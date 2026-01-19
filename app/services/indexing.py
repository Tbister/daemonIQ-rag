"""
Document indexing and ingestion services.
"""
import logging
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings, StorageContext
from llama_index.vector_stores.qdrant import QdrantVectorStore

from app.config import DATA_DIR, COLLECTION
from app.dependencies import client
from app.grounding import extract_grounding_payload, is_grounding_available
from app.observability import get_tracer, instrumentation_wrapper

logger = logging.getLogger(__name__)


def add_grounding_metadata(nodes, use_grounding=True):
    """
    Add ontology grounding metadata to nodes for OG-RAG-lite.

    Phase 1A: Ingest-time tagging
    - Calls BAS-Ontology /api/ground for each node
    - Adds compact grounding payload to node.metadata
    - Gracefully degrades if grounding unavailable

    Args:
        nodes: List of document nodes/chunks
        use_grounding: Enable grounding (default True)

    Returns:
        nodes with grounding metadata added
    """
    if not use_grounding:
        logger.info("Grounding disabled, skipping metadata tagging")
        return nodes

    # Check if grounding service is available
    if not is_grounding_available():
        logger.warning("BAS-Ontology grounding service not available, skipping grounding")
        return nodes

    logger.info(f"Adding grounding metadata to {len(nodes)} nodes...")
    grounded_count = 0

    for i, node in enumerate(nodes):
        # Extract text and metadata
        text = node.get_content()
        title = node.metadata.get("file_name", "")

        # Call grounding service
        grounding_payload = extract_grounding_payload(text, title)

        # Add compact grounding fields to node metadata
        node.metadata.update(grounding_payload)

        # Count nodes with actual grounding (non-empty)
        if grounding_payload.get("equip") or grounding_payload.get("ptags"):
            grounded_count += 1

        # Log progress every 10 nodes
        if (i + 1) % 10 == 0:
            logger.info(f"  Grounded {i + 1}/{len(nodes)} nodes ({grounded_count} with concepts)")

    logger.info(f"✅ Grounding complete: {grounded_count}/{len(nodes)} nodes have grounding metadata")
    return nodes


@instrumentation_wrapper("ingest_documents")
def build_index(force_rebuild=False):
    """
    Build or update the vector index.

    Args:
        force_rebuild: If True, deletes existing collection and rebuilds from scratch.
                      If False, only indexes new documents (incremental update).
    """
    tracer = get_tracer()
    logger.info(f"Starting ingestion from {DATA_DIR} (force_rebuild={force_rebuild})")

    # Load documents
    docs = SimpleDirectoryReader(DATA_DIR, required_exts=[".pdf", ".txt", ".md"]).load_data()
    logger.info(f"Loaded {len(docs)} documents from directory")

    # Check if collection exists
    collection_exists = False
    try:
        client.get_collection(COLLECTION)
        collection_exists = True
        logger.info(f"Collection {COLLECTION} already exists")
    except Exception:
        logger.info(f"Collection {COLLECTION} does not exist")

    if force_rebuild and collection_exists:
        # Delete and recreate collection
        client.delete_collection(COLLECTION)
        logger.info(f"Deleted existing collection {COLLECTION} for rebuild")
        collection_exists = False

    if not collection_exists:
        # Create new collection
        logger.info(f"Creating collection {COLLECTION} with dimension 384")
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config={"size": 384, "distance": "Cosine"}
        )

    # Create vector store
    vector_store = QdrantVectorStore(client=client, collection_name=COLLECTION)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    if collection_exists and not force_rebuild:
        # Incremental update: check which files are already indexed
        logger.info("Performing incremental update...")

        # Get existing filenames from Qdrant (paginate to handle large collections)
        indexed_files = set()
        offset = None

        while True:
            scroll_result = client.scroll(
                collection_name=COLLECTION,
                limit=100,  # Process in batches of 100
                offset=offset,
                with_payload=True,
                with_vectors=False
            )

            points, next_offset = scroll_result

            for point in points:
                if point.payload and "file_name" in point.payload:
                    indexed_files.add(point.payload["file_name"])

            # Break if no more results
            if next_offset is None:
                break

            offset = next_offset

        logger.info(f"Found {len(indexed_files)} files already indexed: {indexed_files}")

        # Filter to only new documents
        new_docs = [doc for doc in docs if doc.metadata.get("file_name") not in indexed_files]

        if len(new_docs) == 0:
            logger.info("✅ All documents already indexed. No new files to add.")
            # Return existing index
            index = VectorStoreIndex.from_vector_store(vector_store)
            collection_info = client.get_collection(COLLECTION)
            logger.info(f"Collection has {collection_info.points_count} vectors")
            return index

        logger.info(f"Found {len(new_docs)} new documents to index: {[d.metadata.get('file_name') for d in new_docs]}")
        docs = new_docs

    logger.info(f"Indexing {len(docs)} documents...")

    # Phase 1A: Parse into nodes explicitly so we can add grounding metadata
    node_parser = Settings.node_parser
    nodes = node_parser.get_nodes_from_documents(docs, show_progress=True)
    logger.info(f"Parsed {len(docs)} documents into {len(nodes)} chunks")

    # Phase 1A: Add grounding metadata to all nodes
    nodes = add_grounding_metadata(nodes, use_grounding=True)

    # Create/update index with grounded nodes
    if collection_exists and not force_rebuild:
        # Load existing index and add new nodes
        index = VectorStoreIndex.from_vector_store(vector_store)
        for node in nodes:
            index.insert_nodes([node])
        logger.info(f"Added {len(nodes)} new grounded nodes to existing index")
    else:
        # Build fresh index from grounded nodes
        index = VectorStoreIndex(
            nodes,
            storage_context=storage_context,
            show_progress=True
        )
        logger.info(f"Created new index with {len(nodes)} grounded nodes")

    # Verify vectors were stored
    collection_info = client.get_collection(COLLECTION)
    vector_count = collection_info.points_count
    logger.info(f"✅ Collection now has {vector_count} vectors")

    if vector_count == 0:
        logger.error("⚠️ WARNING: No vectors were stored! Check embeddings configuration.")

    return index
