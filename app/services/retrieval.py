"""
Retrieval services including grounded retrieval for OG-RAG-lite.
"""
import logging
from typing import Dict, Optional

from llama_index.core import Settings
from llama_index.core.schema import NodeWithScore, TextNode
from qdrant_client.models import Filter, FieldCondition, MatchAny

from app.config import (
    COLLECTION,
    RETRIEVAL_MODE,
    GROUNDED_MIN_CONF,
    GROUNDED_LIMIT_MULT,
    LOG_GROUNDED_RETRIEVAL,
)
from app.dependencies import client
from app.grounding import ground_query

logger = logging.getLogger(__name__)


def build_grounded_filter(query_concepts: Dict[str, any]) -> Optional[Filter]:
    """
    Build Qdrant filter from query grounding concepts.

    Phase 1B: Query-time steering
    - Creates OR filter (Filter.should) matching any concept
    - Prioritizes high-value equipment types
    - Handles noise by filtering out generic concepts if query doesn't mention them

    Args:
        query_concepts: Grounding payload from ground_query()

    Returns:
        Qdrant Filter object or None if no valid concepts
    """
    equip = query_concepts.get("equip", [])
    brick_equip = query_concepts.get("brick_equip", [])
    ptags = query_concepts.get("ptags", [])

    # Noise handling: prioritize high-value equipment types
    HIGH_VALUE_EQUIP = ["vav", "ahu", "fcu", "rtu", "chiller", "boiler", "pump", "fan"]

    # Filter out generic concepts if only generic ones exist
    GENERIC_EQUIP = ["actuator", "meter", "sensor", "controller"]
    has_high_value = any(e in HIGH_VALUE_EQUIP for e in equip)

    if not has_high_value and all(e in GENERIC_EQUIP for e in equip):
        # Only generic concepts - don't filter, use vanilla
        if LOG_GROUNDED_RETRIEVAL:
            logger.info("  Only generic equipment detected, falling back to vanilla retrieval")
        return None

    # Build filter conditions
    conditions = []

    # Equipment filter (MatchAny on equip field)
    if equip:
        conditions.append(
            FieldCondition(key="equip", match=MatchAny(any=equip))
        )

    # Brick equipment filter
    if brick_equip:
        conditions.append(
            FieldCondition(key="brick_equip", match=MatchAny(any=brick_equip))
        )

    # Point tags filter
    if ptags:
        conditions.append(
            FieldCondition(key="ptags", match=MatchAny(any=ptags))
        )

    if not conditions:
        return None

    # OR semantics: match ANY condition
    return Filter(should=conditions)


def rerank_by_overlap(nodes: list, query_concepts: Dict[str, any]) -> list:
    """
    Rerank retrieved nodes by concept overlap with query.

    Phase 1B: Query-time boosting
    - Boosts scores based on overlap with query concepts
    - equip overlap: 1.5x boost
    - brick_equip overlap: 1.3x boost
    - ptags overlap: 1.2x boost

    Args:
        nodes: Retrieved nodes with scores
        query_concepts: Grounding payload from ground_query()

    Returns:
        Reranked nodes sorted by boosted score (stored in node.score)
    """
    query_equip = set(query_concepts.get("equip", []))
    query_brick = set(query_concepts.get("brick_equip", []))
    query_ptags = set(query_concepts.get("ptags", []))

    reranked = []
    for node_with_score in nodes:
        # Get node's grounding metadata
        node_equip = set(node_with_score.node.metadata.get("equip", []))
        node_brick = set(node_with_score.node.metadata.get("brick_equip", []))
        node_ptags = set(node_with_score.node.metadata.get("ptags", []))

        # Calculate overlaps
        equip_overlap = len(query_equip & node_equip)
        brick_overlap = len(query_brick & node_brick)
        ptags_overlap = len(query_ptags & node_ptags)

        # Apply boosts
        boost = 1.0
        if equip_overlap > 0:
            boost *= 1.5
        if brick_overlap > 0:
            boost *= 1.3
        if ptags_overlap > 0:
            boost *= 1.2

        # Calculate boosted score
        original_score = node_with_score.score if node_with_score.score else 0.0
        boosted_score = original_score * boost

        if LOG_GROUNDED_RETRIEVAL:
            logger.info(f"    Node score: {original_score:.4f} -> {boosted_score:.4f} "
                       f"(equip={equip_overlap}, brick={brick_overlap}, ptags={ptags_overlap})")

        # Create new NodeWithScore with boosted score
        reranked_node = NodeWithScore(node=node_with_score.node, score=boosted_score)
        reranked.append(reranked_node)

    # Sort by boosted score (descending)
    reranked.sort(key=lambda n: n.score, reverse=True)
    return reranked


def grounded_retrieve(index, query_text: str, top_k: int = 4) -> list:
    """
    Retrieve nodes using grounded retrieval (Phase 1B).

    Workflow:
    1. Ground the query using BAS-Ontology
    2. Build Qdrant filter from concepts (if confidence >= threshold)
    3. Retrieve limit = top_k * GROUNDED_LIMIT_MULT
    4. Rerank by concept overlap
    5. Return top_k results

    Falls back to vanilla retrieval if:
    - Grounding fails
    - Confidence too low
    - Only generic concepts detected

    Args:
        index: VectorStoreIndex
        query_text: User query
        top_k: Number of final results to return

    Returns:
        List of retrieved nodes
    """
    if RETRIEVAL_MODE != "grounded":
        # Vanilla mode
        if LOG_GROUNDED_RETRIEVAL:
            logger.info(f"[VANILLA] Retrieving {top_k} chunks")
        retriever = index.as_retriever(similarity_top_k=top_k)
        return retriever.retrieve(query_text)

    # Grounded mode
    if LOG_GROUNDED_RETRIEVAL:
        logger.info(f"[GROUNDED] Starting grounded retrieval for: {query_text}")

    # Step 1: Ground the query
    query_concepts = ground_query(query_text)

    if LOG_GROUNDED_RETRIEVAL:
        logger.info(f"  Query grounding:")
        logger.info(f"    equip: {query_concepts.get('equip', [])}")
        logger.info(f"    brick_equip: {query_concepts.get('brick_equip', [])}")
        logger.info(f"    ptags: {query_concepts.get('ptags', [])[:3]}...")  # Show first 3
        logger.info(f"    raw: {query_concepts.get('raw', [])[:5]}...")  # Show first 5
        logger.info(f"    gconf: {query_concepts.get('gconf', 0.0):.2f}")

    # Step 2: Check confidence threshold
    gconf = query_concepts.get("gconf", 0.0)
    if gconf < GROUNDED_MIN_CONF:
        if LOG_GROUNDED_RETRIEVAL:
            logger.info(f"  Confidence {gconf:.2f} < {GROUNDED_MIN_CONF}, falling back to vanilla")
        retriever = index.as_retriever(similarity_top_k=top_k)
        return retriever.retrieve(query_text)

    # Step 3: Build filter
    qdrant_filter = build_grounded_filter(query_concepts)

    if qdrant_filter is None:
        # No valid filter (e.g., only generic concepts)
        if LOG_GROUNDED_RETRIEVAL:
            logger.info(f"  No valid filter, falling back to vanilla")
        retriever = index.as_retriever(similarity_top_k=top_k)
        return retriever.retrieve(query_text)

    # Step 4: Retrieve with filter and higher limit
    retrieve_limit = top_k * GROUNDED_LIMIT_MULT

    if LOG_GROUNDED_RETRIEVAL:
        logger.info(f"  Filter applied: {len(qdrant_filter.should)} conditions")
        logger.info(f"  Retrieving {retrieve_limit} chunks for reranking")

    # Get embedding for query
    embed_model = Settings.embed_model
    query_embedding = embed_model.get_query_embedding(query_text)

    # Query Qdrant directly with filter
    search_result = client.query_points(
        collection_name=COLLECTION,
        query=query_embedding,
        query_filter=qdrant_filter,
        limit=retrieve_limit,
        with_payload=True
    )

    # Convert to NodeWithScore objects
    nodes = []
    for point in search_result.points:
        # Create TextNode from Qdrant point
        node = TextNode(
            text=point.payload.get("_node_content", ""),
            id_=str(point.id),
            metadata=point.payload
        )
        nodes.append(NodeWithScore(node=node, score=point.score))

    if LOG_GROUNDED_RETRIEVAL:
        logger.info(f"  Retrieved {len(nodes)} filtered chunks")

    if len(nodes) == 0:
        # Filter was too restrictive, fall back to vanilla
        if LOG_GROUNDED_RETRIEVAL:
            logger.info(f"  No results with filter, falling back to vanilla")
        retriever = index.as_retriever(similarity_top_k=top_k)
        return retriever.retrieve(query_text)

    # Step 5: Rerank by overlap
    if LOG_GROUNDED_RETRIEVAL:
        logger.info(f"  Reranking by concept overlap...")

    nodes = rerank_by_overlap(nodes, query_concepts)

    # Step 6: Select top_k
    final_nodes = nodes[:top_k]

    if LOG_GROUNDED_RETRIEVAL:
        logger.info(f"  Final top {top_k} chunks:")
        for i, node in enumerate(final_nodes, 1):
            filename = node.node.metadata.get("file_name", "?")
            page = node.node.metadata.get("page_label", "?")
            equip = node.node.metadata.get("equip", [])
            ptags = node.node.metadata.get("ptags", [])[:2]  # Show first 2
            logger.info(f"    {i}. score={node.score:.4f} | {filename} p{page} | equip={equip} ptags={ptags}")

    return final_nodes
