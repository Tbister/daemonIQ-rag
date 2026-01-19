"""
Ontology grounding utility for OG-RAG-lite integration.

Calls BAS-Ontology /api/ground endpoint to extract semantic metadata
(equipment types, point types, brick classes) for chunks during ingestion.

Phase 1A: Ingest-time tagging only (no retrieval changes).
"""

import os
import logging
from typing import Dict, List, Optional
import requests

logger = logging.getLogger(__name__)

BAS_ONTOLOGY_URL = os.getenv("BAS_ONTOLOGY_URL", "http://localhost:8001")
GROUNDING_TIMEOUT = 2.0  # seconds


def ground_text(text: str, max_length: int = 800) -> Dict[str, any]:
    """
    Ground a text chunk using BAS-Ontology /api/ground endpoint.

    Args:
        text: Text to ground (chunk content)
        max_length: Maximum text length to send (default 800)

    Returns:
        Dict with compact payload fields:
        {
            "equip": List[str],           # Haystack equipment kinds
            "brick_equip": List[str],     # Brick equipment classes
            "ptags": List[str],           # Point tag combinations
            "raw": List[str],             # Raw normalized tags
            "gconf": float                # Average confidence
        }

    Returns empty lists if grounding fails (never raises exceptions).
    """

    # Prepare payload with compact keys for Qdrant storage
    payload = {
        "equip": [],
        "brick_equip": [],
        "ptags": [],
        "raw": [],
        "gconf": 0.0
    }

    # Truncate text to max_length
    query_text = text[:max_length].strip()
    if not query_text:
        return payload

    try:
        # Call BAS-Ontology /api/ground
        response = requests.post(
            f"{BAS_ONTOLOGY_URL}/api/ground",
            json={"query": query_text},
            timeout=GROUNDING_TIMEOUT,
            headers={"Content-Type": "application/json"}
        )

        if response.status_code != 200:
            logger.warning(f"Grounding API returned status {response.status_code}")
            return payload

        data = response.json()

        # Extract equipment types
        equipment_types = data.get("equipment_types", [])
        for equip in equipment_types:
            haystack_kind = equip.get("haystack_kind")
            if haystack_kind:
                payload["equip"].append(haystack_kind)

            brick_class = equip.get("brick_class")
            if brick_class:
                payload["brick_equip"].append(brick_class)

        # Extract point types (flatten tag lists into readable strings)
        point_types = data.get("point_types", [])
        for point in point_types:
            tags = point.get("haystack_tags", [])
            if tags:
                # Create readable point tag string: "discharge air temp sensor"
                ptag = " ".join(tags)
                payload["ptags"].append(ptag)

        # Extract raw tags (normalize: lowercase, no duplicates)
        raw_tags = data.get("raw_tags", [])
        payload["raw"] = sorted(list(set(t.lower() for t in raw_tags)))

        # Calculate average confidence
        confidences = []
        for equip in equipment_types:
            if "confidence" in equip:
                confidences.append(equip["confidence"])
        for point in point_types:
            if "confidence" in point:
                confidences.append(point["confidence"])

        if confidences:
            payload["gconf"] = sum(confidences) / len(confidences)

        logger.debug(f"Grounded text: {len(payload['equip'])} equip, {len(payload['ptags'])} points, {len(payload['raw'])} raw tags")

    except requests.exceptions.Timeout:
        logger.warning(f"Grounding API timeout after {GROUNDING_TIMEOUT}s")
    except requests.exceptions.ConnectionError:
        logger.warning(f"Cannot connect to BAS-Ontology at {BAS_ONTOLOGY_URL}")
    except Exception as e:
        logger.warning(f"Grounding failed: {e}")

    return payload


def extract_grounding_payload(text: str, title: str = "") -> Dict[str, any]:
    """
    Extract grounding payload for a chunk (combines title + text).

    This is the main function called during ingestion.

    Args:
        text: Chunk text content
        title: Document title or chunk heading (optional)

    Returns:
        Compact payload dict to store in Qdrant
    """

    # Combine title + text for better context
    combined = f"{title} {text}".strip() if title else text

    return ground_text(combined)


def is_grounding_available() -> bool:
    """
    Check if BAS-Ontology grounding service is available.

    Returns:
        True if service is reachable, False otherwise
    """
    try:
        response = requests.get(
            f"{BAS_ONTOLOGY_URL}/health",
            timeout=2.0
        )
        return response.status_code == 200
    except Exception:
        return False


def ground_query(query: str) -> Dict[str, any]:
    """
    Ground a user query using BAS-Ontology /api/ground endpoint.

    Phase 1B: Query-time grounding for retrieval filtering/boosting.

    Args:
        query: User query text

    Returns:
        Dict with compact payload fields (same structure as ground_text):
        {
            "equip": List[str],           # Haystack equipment kinds
            "brick_equip": List[str],     # Brick equipment classes
            "ptags": List[str],           # Point tag combinations
            "raw": List[str],             # Raw normalized tags
            "gconf": float                # Average confidence
        }
    """
    # Use ground_text with no length limit for queries (they're usually short)
    return ground_text(query, max_length=500)
