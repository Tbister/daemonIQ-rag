# BAS-Ontology OG-RAG Fit Assessment

**Assessment Date:** 2026-01-08 16:04:51

**Endpoint:** `http://localhost:8001/api/ground`

## Executive Summary

- **Total Queries:** 75
- **Success Rate:** 100.0%
- **Avg Response Time:** 21.0ms
- **Equipment Detection Rate:** 28.0%
- **Point Detection Rate:** 12.0%
- **Brick Mapping Rate:** 32.0%

## Performance by Query Category

| Category | Queries | Success | Equip | Points | Brick | Avg Concepts |
|----------|---------|---------|-------|--------|-------|--------------|
| jargon       |      25 | 100.0% | 52.0% |  24.0% | 60.0% |          2.0 |
| paraphrase   |      25 | 100.0% | 24.0% |  12.0% | 32.0% |          1.3 |
| ambiguity    |      25 | 100.0% |  8.0% |   0.0% |  4.0% |          0.1 |

## Recall Drop: Jargon → Paraphrase

- **Equipment Detection Drop:** +28.0%
- **Point Detection Drop:** +12.0%

⚠️ **SIGNIFICANT RECALL DROP** when queries use natural language vs BAS jargon

## Confidence Score Distribution

- **Mean:** 0.654
- **Median:** 0.600
- **Std Dev:** 0.223
- **Range:** [0.333, 1.000]

## Concept Count Statistics

- **Mean Concepts per Query:** 1.1
- **Median:** 0.0
- **Range:** [0, 11]
- **Queries with Zero Concepts:** 48

## Top Failure Modes

| Failure Mode | Count |
|--------------|-------|
| no_concepts_returned | 48 |

## Sample Grounding Outputs

### Jargon Examples

**1. Query:** "VAV discharge air temperature too high"
- Concepts: 1
- Equipment: ✓
- Points: ✗
- Brick: Variable_Air_Volume_Box

**2. Query:** "AHU economizer occupied unoccupied sequence"
- Concepts: 1
- Equipment: ✓
- Points: ✗
- Brick: Air_Handling_Unit

**3. Query:** "Supply fan proof not made"
- Concepts: 4
- Equipment: ✗
- Points: ✓
- Brick: Fan_Status, Supply_Fan_Status, Return_Fan_Status

### Paraphrase Examples

**1. Query:** "The air coming out is too warm at the terminal"
- Concepts: 0
- Equipment: ✗
- Points: ✗

**2. Query:** "How do I set free cooling when the building is occupied?"
- Concepts: 0
- Equipment: ✗
- Points: ✗

**3. Query:** "The fan won't start even though it's enabled"
- Concepts: 0
- Equipment: ✗
- Points: ✗

### Ambiguity Examples

**1. Query:** "Fan not working"
- Concepts: 0
- Equipment: ✗
- Points: ✗

**2. Query:** "Temperature too high"
- Concepts: 0
- Equipment: ✗
- Points: ✗

**3. Query:** "Controller offline"
- Concepts: 0
- Equipment: ✗
- Points: ✗