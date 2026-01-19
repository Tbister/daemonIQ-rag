#!/usr/bin/env python3
"""
Smoke test for Phase 1B grounded retrieval.

Tests 3 queries:
- VAV discharge air temperature too high
- chiller low suction pressure
- ahu supply fan status

Prints grounding payload and top hits with their grounding metadata.

Usage:
    python scripts/smoke_grounded_query.py
"""

import os
import sys
import requests
from typing import Dict, List

# Configuration
RAG_SERVICE_URL = os.getenv("RAG_SERVICE_URL", "http://localhost:8000")
BAS_ONTOLOGY_URL = os.getenv("BAS_ONTOLOGY_URL", "http://localhost:8001")

# Test queries
SMOKE_QUERIES = [
    "VAV discharge air temperature too high",
    "chiller low suction pressure",
    "ahu supply fan status"
]


def ground_query(query: str) -> Dict:
    """Ground a query using BAS-Ontology."""
    try:
        response = requests.post(
            f"{BAS_ONTOLOGY_URL}/api/ground",
            json={"query": query},
            timeout=5.0
        )
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"Status {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}


def retrieve_chunks(query: str, k: int = 4) -> Dict:
    """Retrieve chunks from RAG service."""
    try:
        response = requests.post(
            f"{RAG_SERVICE_URL}/retrieve",
            json={"q": query, "k": k},
            timeout=30.0
        )
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"Status {response.status_code}", "detail": response.text}
    except Exception as e:
        return {"error": str(e)}


def extract_compact_payload(grounding_response: Dict) -> Dict:
    """Extract compact payload from BAS-Ontology response."""
    payload = {
        "equip": [],
        "brick_equip": [],
        "ptags": [],
        "raw": [],
        "gconf": 0.0
    }

    if "error" in grounding_response:
        return payload

    # Extract equipment types
    equipment_types = grounding_response.get("equipment_types", [])
    for equip in equipment_types:
        haystack_kind = equip.get("haystack_kind")
        if haystack_kind:
            payload["equip"].append(haystack_kind)

        brick_class = equip.get("brick_class")
        if brick_class:
            payload["brick_equip"].append(brick_class)

    # Extract point types
    point_types = grounding_response.get("point_types", [])
    for point in point_types:
        tags = point.get("haystack_tags", [])
        if tags:
            ptag = " ".join(tags)
            payload["ptags"].append(ptag)

    # Extract raw tags
    raw_tags = grounding_response.get("raw_tags", [])
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

    return payload


def print_grounding_payload(payload: Dict):
    """Pretty print grounding payload."""
    print("  📊 Query Grounding:")
    print(f"     equip: {payload.get('equip', [])}")
    print(f"     brick_equip: {payload.get('brick_equip', [])}")
    print(f"     ptags: {payload.get('ptags', [])[:3]}{'...' if len(payload.get('ptags', [])) > 3 else ''}")
    print(f"     raw: {payload.get('raw', [])[:5]}{'...' if len(payload.get('raw', [])) > 5 else ''}")
    print(f"     gconf: {payload.get('gconf', 0.0):.2f}")


def print_retrieval_results(results: Dict):
    """Pretty print retrieval results."""
    if "error" in results:
        print(f"  ❌ Retrieval error: {results['error']}")
        if "detail" in results:
            print(f"     Detail: {results['detail']}")
        return

    count = results.get("count", 0)
    mode = results.get("mode", "unknown")
    print(f"\n  📄 Retrieved {count} chunks (mode: {mode})")

    chunks = results.get("results", [])
    for i, chunk in enumerate(chunks[:5], 1):  # Show top 5
        score = chunk.get("score", 0.0)
        metadata = chunk.get("metadata", {})
        filename = metadata.get("file_name", "unknown")
        page = metadata.get("page_label", "?")
        equip = metadata.get("equip", [])
        brick_equip = metadata.get("brick_equip", [])
        ptags = metadata.get("ptags", [])[:2]  # Show first 2
        raw = metadata.get("raw", [])[:5]  # Show first 5

        print(f"\n     Chunk {i} (score: {score:.4f})")
        print(f"       File: {filename}, Page: {page}")
        print(f"       equip: {equip}")
        if brick_equip:
            print(f"       brick_equip: {brick_equip}")
        if ptags:
            print(f"       ptags: {ptags}{'...' if len(metadata.get('ptags', [])) > 2 else ''}")
        if raw:
            print(f"       raw: {raw}{'...' if len(metadata.get('raw', [])) > 5 else ''}")

        # Show text preview
        text = chunk.get("text", "")
        preview = text[:200].replace('\n', ' ')
        print(f"       Preview: {preview}...")


def main():
    print("=" * 80)
    print("PHASE 1B: Grounded Retrieval Smoke Test")
    print("=" * 80)
    print(f"\nRAG Service: {RAG_SERVICE_URL}")
    print(f"BAS-Ontology: {BAS_ONTOLOGY_URL}")

    # Check services are running
    print("\n🔍 Checking service health...")
    try:
        rag_health = requests.get(f"{RAG_SERVICE_URL}/health", timeout=5)
        if rag_health.status_code == 200:
            print("  ✅ RAG service is running")
        else:
            print(f"  ❌ RAG service returned status {rag_health.status_code}")
            sys.exit(1)
    except Exception as e:
        print(f"  ❌ Cannot connect to RAG service: {e}")
        sys.exit(1)

    try:
        onto_health = requests.get(f"{BAS_ONTOLOGY_URL}/health", timeout=5)
        if onto_health.status_code == 200:
            print("  ✅ BAS-Ontology is running")
        else:
            print(f"  ⚠️  BAS-Ontology returned status {onto_health.status_code}")
    except Exception as e:
        print(f"  ⚠️  BAS-Ontology not available: {e}")

    # Run smoke queries
    print("\n" + "=" * 80)
    print("RUNNING SMOKE QUERIES")
    print("=" * 80)

    for query_num, query in enumerate(SMOKE_QUERIES, 1):
        print(f"\n{'='*80}")
        print(f"Query {query_num}/{len(SMOKE_QUERIES)}: \"{query}\"")
        print("=" * 80)

        # Ground the query
        grounding_response = ground_query(query)
        payload = extract_compact_payload(grounding_response)
        print_grounding_payload(payload)

        # Retrieve chunks
        print("\n  🔎 Retrieving chunks...")
        results = retrieve_chunks(query, k=4)
        print_retrieval_results(results)

        print()  # Blank line between queries

    # Summary
    print("\n" + "=" * 80)
    print("SMOKE TEST COMPLETE")
    print("=" * 80)
    print("\n✅ All smoke queries completed!")
    print("\nTo enable debug logging, set LOG_GROUNDED_RETRIEVAL=1 in .env")
    print("To switch to grounded mode, set RETRIEVAL_MODE=grounded in .env")


if __name__ == "__main__":
    main()
