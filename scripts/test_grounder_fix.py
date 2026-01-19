#!/usr/bin/env python3
"""
Simple test to verify BAS-Ontology grounder fixes.

Tests critical equipment detection for OG-RAG integration.
"""

import requests
import sys

BAS_ONTOLOGY_URL = "http://localhost:8001"

def test_query(query: str, expected_equipment: str) -> bool:
    """Test a single query and check if expected equipment is detected."""

    response = requests.post(
        f"{BAS_ONTOLOGY_URL}/api/ground",
        json={"query": query},
        timeout=5
    )

    if response.status_code != 200:
        print(f"❌ FAIL: {query}")
        print(f"   API error: {response.status_code}")
        return False

    data = response.json()
    equipment_types = data.get("equipment_types", [])
    detected_kinds = [e["haystack_kind"] for e in equipment_types]

    if expected_equipment in detected_kinds:
        print(f"✅ PASS: {query}")
        print(f"   Detected: {detected_kinds}")
        return True
    else:
        print(f"❌ FAIL: {query}")
        print(f"   Expected: {expected_equipment}")
        print(f"   Detected: {detected_kinds}")
        print(f"   Raw tags: {data.get('raw_tags', [])}")
        return False

def main():
    print("Testing BAS-Ontology Grounder Fixes")
    print("=" * 50)

    tests = [
        ("VAV discharge air temperature", "vav"),
        ("chiller low suction pressure", "chiller"),
        ("ahu supply fan status", "ahu"),
    ]

    passed = 0
    failed = 0

    for query, expected in tests:
        if test_query(query, expected):
            passed += 1
        else:
            failed += 1
        print()

    print("=" * 50)
    print(f"Results: {passed} passed, {failed} failed")

    if failed > 0:
        print("\n⚠️  Some tests failed. Check grounder.py edits.")
        sys.exit(1)
    else:
        print("\n🎉 All tests passed! Grounder is working correctly.")
        sys.exit(0)

if __name__ == "__main__":
    try:
        main()
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to BAS-Ontology at {BAS_ONTOLOGY_URL}")
        print("   Make sure it's running: BAS_PORT=8001 ./start.sh")
        sys.exit(1)
