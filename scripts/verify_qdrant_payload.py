#!/usr/bin/env python3
"""
Verify Qdrant payload contains grounding metadata from Phase 1A.

Usage:
    python scripts/verify_qdrant_payload.py
"""

import os
import sys
import requests
from typing import Dict, Any

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION = os.getenv("QDRANT_COLLECTION", "bas_docs")


def get_sample_points(limit: int = 5) -> Dict[str, Any]:
    """Fetch sample points from Qdrant to inspect payload."""
    url = f"{QDRANT_URL}/collections/{COLLECTION}/points/scroll"
    params = {
        "limit": limit,
        "with_payload": True,
        "with_vectors": False
    }

    try:
        response = requests.post(url, json=params, timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Qdrant returned status {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Cannot connect to Qdrant: {e}")
        return None


def analyze_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze payload structure and grounding fields."""
    analysis = {
        "has_grounding": False,
        "grounding_fields": [],
        "equip_count": 0,
        "brick_equip_count": 0,
        "ptags_count": 0,
        "raw_count": 0,
        "gconf": None,
        "standard_fields": []
    }

    # Check for grounding fields (Phase 1A)
    grounding_keys = ["equip", "brick_equip", "ptags", "raw", "gconf"]
    for key in grounding_keys:
        if key in payload:
            analysis["grounding_fields"].append(key)
            if key == "equip" and payload[key]:
                analysis["equip_count"] = len(payload[key])
            elif key == "brick_equip" and payload[key]:
                analysis["brick_equip_count"] = len(payload[key])
            elif key == "ptags" and payload[key]:
                analysis["ptags_count"] = len(payload[key])
            elif key == "raw" and payload[key]:
                analysis["raw_count"] = len(payload[key])
            elif key == "gconf":
                analysis["gconf"] = payload[key]

    analysis["has_grounding"] = len(analysis["grounding_fields"]) > 0

    # Check for standard LlamaIndex fields
    standard_keys = ["file_name", "page_label", "file_path"]
    for key in standard_keys:
        if key in payload:
            analysis["standard_fields"].append(key)

    return analysis


def main():
    print("=" * 70)
    print("PHASE 1A: Qdrant Payload Verification")
    print("=" * 70)
    print(f"\nCollection: {COLLECTION}")
    print(f"Qdrant URL: {QDRANT_URL}")

    # Fetch sample points
    print(f"\nFetching sample points...")
    data = get_sample_points(limit=10)

    if not data:
        sys.exit(1)

    points = data.get("result", {}).get("points", [])
    print(f"Retrieved {len(points)} points\n")

    if not points:
        print("❌ No points found in collection. Run ingestion first.")
        sys.exit(1)

    # Analyze payloads
    print("=" * 70)
    print("PAYLOAD ANALYSIS")
    print("=" * 70)

    grounded_count = 0
    non_grounded_count = 0

    for i, point in enumerate(points, 1):
        payload = point.get("payload", {})
        analysis = analyze_payload(payload)

        print(f"\n📄 Point {i} (ID: {point['id'][:16]}...)")
        print(f"   File: {payload.get('file_name', 'N/A')}")
        print(f"   Page: {payload.get('page_label', 'N/A')}")

        if analysis["has_grounding"]:
            grounded_count += 1
            print(f"   ✅ HAS GROUNDING METADATA")
            print(f"      • equip: {analysis['equip_count']} items")
            if analysis["equip_count"] > 0 and "equip" in payload:
                print(f"        → {payload['equip']}")
            print(f"      • brick_equip: {analysis['brick_equip_count']} items")
            if analysis["brick_equip_count"] > 0 and "brick_equip" in payload:
                print(f"        → {payload['brick_equip']}")
            print(f"      • ptags: {analysis['ptags_count']} items")
            if analysis["ptags_count"] > 0 and "ptags" in payload:
                print(f"        → {payload['ptags'][:3]}...")  # Show first 3
            print(f"      • raw: {analysis['raw_count']} tags")
            if analysis["raw_count"] > 0 and "raw" in payload:
                print(f"        → {payload['raw'][:5]}...")  # Show first 5
            if analysis["gconf"] is not None:
                print(f"      • gconf: {analysis['gconf']:.2f}")
        else:
            non_grounded_count += 1
            print(f"   ⚠️  NO GROUNDING METADATA")
            print(f"      Available fields: {list(payload.keys())}")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total points analyzed: {len(points)}")
    print(f"Points with grounding: {grounded_count} ({grounded_count/len(points)*100:.1f}%)")
    print(f"Points without grounding: {non_grounded_count}")

    if grounded_count > 0:
        print("\n✅ SUCCESS: Grounding metadata is present in Qdrant payloads!")
        print("   Phase 1A (ingest-time tagging) is working correctly.")
    else:
        print("\n❌ FAILURE: No grounding metadata found.")
        print("   Check that:")
        print("   1. BAS-Ontology is running at http://localhost:8001")
        print("   2. Ingestion was run with force_rebuild=true")
        print("   3. Logs show grounding was applied")

    # Show curl command for manual verification
    print("\n" + "=" * 70)
    print("MANUAL VERIFICATION")
    print("=" * 70)
    print(f"\nTo manually inspect payloads:")
    print(f"""
curl -s "http://localhost:6333/collections/{COLLECTION}/points/scroll?limit=1&with_payload=true&with_vectors=false" | jq '.result.points[0].payload'
    """.strip())


if __name__ == "__main__":
    main()
