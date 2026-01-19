# BAS-Ontology Grounder Fix Results

**Date:** 2026-01-08
**Fix Applied:** Use equipment_points.yaml as source of truth + improved synonyms

---

## Summary

Applied minimal, production-safe fix to BAS-Ontology grounder to enable OG-RAG integration.

### Changes Made

1. **Updated equipment detection logic** (`app/grounder.py:154-166`)
   - Primary source: `equipment_points.yaml` (authoritative list)
   - Secondary: Ontology parent hierarchy (fallback)
   - **Result:** Now detects vav, chiller, fcu, rtu, boiler, pump regardless of parent chain

2. **Expanded equipment synonyms** (`app/grounder.py:35-47`)
   - Added variations: "variable air volume", "terminal box", "cooling machine", etc.
   - **Result:** Better natural language coverage

### Test Results

#### Manual Tests (3 Critical Queries)
✅ **100% Success Rate**

| Query | Equipment Detected | Status |
|-------|-------------------|--------|
| "VAV discharge air temperature" | vav (1.0 confidence) | ✅ PASS |
| "chiller low suction pressure" | chiller (1.0 confidence) | ✅ PASS |
| "ahu supply fan status" | ahu (1.0 confidence) + 4 point types | ✅ PASS |

#### Full Test Suite (75 Queries)

**Before Fix:**
- Equipment Detection: 0%
- Point Detection: 0%
- Brick Mapping: 0%

**After Fix:**
- **Equipment Detection: 28%** (🎯 **52% for jargon queries**)
- **Point Detection: 12%** (24% for jargon queries)
- **Brick Mapping: 32%** (60% for jargon queries)

### Performance by Query Type

| Category | Queries | Equipment | Points | Brick | Avg Concepts |
|----------|---------|-----------|--------|-------|--------------|
| **Jargon** (technical BAS language) | 25 | **52%** | 24% | 60% | 2.0 |
| **Paraphrase** (natural language) | 25 | 24% | 12% | 32% | 1.3 |
| **Ambiguity** (underspecified) | 25 | 8% | 0% | 4% | 0.1 |

### Key Findings

✅ **What Works Now:**
- Technical queries with BAS jargon: "VAV discharge air temp", "AHU economizer", "chiller pressure"
- Equipment acronyms: VAV, AHU, FCU, RTU, chiller, boiler, pump
- Point patterns with "status", "sensor", "cmd": "supply fan status", "discharge temp sensor"

⚠️ **Still Needs Work:**
- Natural language paraphrases: "The air coming out is too warm" (0% detection)
- Ambiguous queries: "Fan not working" (needs equipment context)
- **28% recall drop** from jargon → paraphrase queries

### Example Grounding Outputs

#### Query: "VAV discharge air temperature"
```json
{
  "equipment_types": [
    {
      "haystack_kind": "vav",
      "confidence": 1.0,
      "brick_class": "Variable_Air_Volume_Box",
      "brick_aliases": ["VAV", "Variable_Air_Volume_Box_With_Reheat"],
      "match_type": "exact"
    }
  ],
  "raw_tags": ["air", "discharge", "temp", "vav"],
  "mappings": [...]
}
```

#### Query: "chiller low suction pressure"
```json
{
  "equipment_types": [
    {
      "haystack_kind": "chiller",
      "confidence": 1.0,
      "brick_class": "Chiller",
      "brick_aliases": ["Centrifugal_Chiller", "Absorption_Chiller"],
      "match_type": "exact"
    }
  ],
  "raw_tags": ["chiller", "pressure"]
}
```

#### Query: "ahu supply fan status"
```json
{
  "equipment_types": [
    {
      "haystack_kind": "ahu",
      "confidence": 1.0,
      "brick_class": "Air_Handling_Unit",
      "match_type": "exact"
    }
  ],
  "point_types": [
    {
      "haystack_tags": ["supply", "fan", "run", "status"],
      "confidence": 0.5,
      "brick_class": "Supply_Fan_Status",
      "description": "Indicates supply fan is running",
      "match_type": "template_match"
    },
    // 3 more point variants...
  ]
}
```

---

## OG-RAG Readiness Assessment

### ✅ READY FOR PHASE 1 (OG-RAG-Lite)

**Jargon Query Performance: 52% equipment detection is sufficient for:**
- Ingest-time metadata tagging (boost docs with detected equipment)
- Query-time filter/boost (prefer docs matching grounded concepts)
- Hypernode-based retrieval (use detected equipment as index keys)

**Recommended Usage:**
- ✅ Use for **technical BAS queries** (52% coverage)
- ✅ Use **raw_tags** as fallback (100% coverage)
- ⚠️ Warn users that **natural language queries** have lower accuracy

### ⚠️ NOT READY FOR PRODUCTION (Natural Language)

**24% paraphrase detection is too low for:**
- General-purpose user queries
- Non-expert user interfaces
- Consumer-facing applications

**Needed for Production:**
- Semantic matching (embeddings, not regex)
- Expanded synonym dictionaries from query logs
- NER/NLP for entity extraction from natural language

---

## Next Steps

### Immediate (Ready Now)
1. ✅ BAS-Ontology is fixed and running on port 8001
2. ✅ Grounder detecting core equipment types (vav, ahu, chiller, boiler, pump, fcu, rtu)
3. ✅ Test harness available: `scripts/test_grounder_fix.py`

### Phase 1 Implementation (Weeks 1-2)
1. **Add grounding to daemonIQ-rag ingestion**
   - Call `/api/ground` for each chunk
   - Store equipment_haystack, equipment_brick in Qdrant metadata
   - Re-ingest docs: `make ingest-rebuild`

2. **Add query-time grounding + filter/boost**
   - Ground user query before retrieval
   - Filter/boost docs matching grounded concepts
   - Measure improvement vs baseline

### Future Improvements (Phase 2+)
1. **Fix natural language recall** (Priority: HIGH)
   - Add semantic matching with embeddings
   - Expand synonym dictionaries
   - Use spaCy/NER for entity extraction

2. **Improve point detection** (Priority: MEDIUM)
   - Current: 24% for jargon, 12% overall
   - Target: 60%+ detection
   - Fix template matching logic

3. **Add topology relationships** (Priority: LOW)
   - Enable hyperedge-based retrieval
   - `(ahu, feeds, vav)` relationships
   - 2-hop neighborhood expansion

---

## Files Modified

- `/Users/tomister/BAS-Ontology/app/grounder.py` (lines 154-166, 35-47)
  - Added equipment_points.yaml as primary source of truth
  - Expanded equipment synonyms
  - Backup available: `grounder.py.backup`

## Test Artifacts

- `scripts/test_grounder_fix.py` - Simple 3-query test (PASS)
- `scripts/ontology_fit_test.py` - Full 75-query test suite
- `outputs/ontology_fit_results.jsonl` - Raw test results
- `outputs/ontology_fit_summary.md` - Metrics report
- `outputs/PHASE_0_OG_RAG_ASSESSMENT.md` - Full Phase 0 assessment

---

## Verdict: ✅ PHASE 0 COMPLETE → READY FOR PHASE 1

**Equipment detection improved from 0% → 52% for jargon queries.**
**BAS-Ontology is now viable for OG-RAG-lite implementation.**

Next: Integrate grounding into daemonIQ-rag ingest + retrieval pipeline.
