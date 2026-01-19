# PRP: Grounding Confidence Evaluation Framework

> **Status:** Draft
> **Author:** Engineering Team
> **Created:** 2026-01-10
> **Target Phase:** Post-1B Enhancement

---

## 1. Objective

Implement a systematic evaluation framework to measure and tune the grounding confidence threshold. Currently, `GROUNDED_MIN_CONF=0.6` is a heuristic; this PRP establishes data-driven tuning.

**Success Metric:** Identify optimal threshold that maximizes F1-score on 50+ labeled BAS queries, achieving F1 >= 0.75.

---

## 2. Current State

**Relevant Files:**
- `app/main.py:298-302` - Confidence threshold check
- `app/grounding.py:96-105` - Confidence calculation
- `.env` - `GROUNDED_MIN_CONF=0.6`

**Limitations Addressed:**
1. Threshold (0.6) was chosen without evaluation data
2. No way to measure precision/recall of grounding decisions
3. Can't A/B test different thresholds

---

## 3. Proposed Change

Add an evaluation harness that:
1. Accepts labeled query-concept pairs as ground truth
2. Runs queries through grounding pipeline
3. Computes precision/recall/F1 at various thresholds
4. Outputs optimal threshold recommendation

### Architecture Impact

```
New script: scripts/eval_grounding.py
                |
                v
    +------------------------+
    | Load ground truth YAML |
    +------------------------+
                |
                v
    +------------------------+
    | For each query:        |
    |   - Ground via API     |
    |   - Compare to labels  |
    +------------------------+
                |
                v
    +------------------------+
    | Compute metrics at     |
    | thresholds: 0.3-0.9    |
    +------------------------+
                |
                v
    +------------------------+
    | Output:                |
    | - Metrics table        |
    | - Recommended threshold|
    +------------------------+
```

### Data Contract Changes

| Field | Before | After | Migration |
|-------|--------|-------|-----------|
| N/A | N/A | N/A | No schema changes |

### API Changes

| Endpoint | Change |
|----------|--------|
| N/A | No API changes (evaluation is offline) |

---

## 4. Constraints

- [x] Must not violate INV-3 (grounding precedes retrieval)
- [x] Must not modify production code (evaluation only)
- [x] Must work when BAS-Ontology is available
- [x] Must complete evaluation in < 5 minutes for 100 queries

---

## 5. Acceptance Criteria

- [x] **AC-1:** Ground truth file format defined and documented
  - Test: `cat data/eval/grounding_labels.yaml`
  - Expected: Valid YAML with query/expected_concepts pairs

- [ ] **AC-2:** Evaluation script runs without errors
  - Test: `python scripts/eval_grounding.py`
  - Expected: Outputs metrics table, no exceptions

- [ ] **AC-3:** Metrics include precision, recall, F1 at each threshold
  - Test: `python scripts/eval_grounding.py --output json | jq '.thresholds'`
  - Expected: Array with metrics for thresholds 0.3, 0.4, ..., 0.9

- [ ] **AC-4:** Script recommends optimal threshold
  - Test: `python scripts/eval_grounding.py | grep "Recommended"`
  - Expected: "Recommended threshold: X.X (F1=Y.YY)"

---

## 6. Impacted Files

| File | Change Type | Description |
|------|-------------|-------------|
| `scripts/eval_grounding.py` | Add | Evaluation script |
| `data/eval/grounding_labels.yaml` | Add | Ground truth labels |
| `data/eval/README.md` | Add | Label format documentation |
| `context/STATE.md` | Update | Document evaluation capability |

---

## 7. Step Plan

### Step 1: Define Ground Truth Format
**Files:** `data/eval/grounding_labels.yaml`, `data/eval/README.md`
**Actions:**
1. Create YAML schema for labeled queries
2. Add 50 initial labeled queries (10 VAV, 10 AHU, 10 chiller, 10 generic, 10 edge cases)
3. Document format in README

**Validation:** `python -c "import yaml; yaml.safe_load(open('data/eval/grounding_labels.yaml'))"`

### Step 2: Implement Evaluation Script
**Files:** `scripts/eval_grounding.py`
**Actions:**
1. Load ground truth from YAML
2. Call `ground_query()` for each query
3. Compare predicted concepts to expected
4. Compute metrics per threshold

**Validation:** `python scripts/eval_grounding.py --dry-run`

### Step 3: Generate Threshold Analysis
**Run:** `python scripts/eval_grounding.py --output table`
**Expected:**
```
Threshold | Precision | Recall | F1
----------|-----------|--------|----
0.3       | 0.45      | 0.92   | 0.60
0.4       | 0.55      | 0.88   | 0.68
0.5       | 0.65      | 0.82   | 0.72
0.6       | 0.72      | 0.75   | 0.73  <- current
0.7       | 0.80      | 0.65   | 0.72
0.8       | 0.88      | 0.50   | 0.64
0.9       | 0.95      | 0.30   | 0.46
```

---

## 8. Validation Steps

1. **Script Execution:**
   ```bash
   python scripts/eval_grounding.py
   ```
   Expected: Clean output with metrics

2. **JSON Output:**
   ```bash
   python scripts/eval_grounding.py --output json > eval_results.json
   jq '.optimal_threshold' eval_results.json
   ```
   Expected: Float between 0.3 and 0.9

3. **Threshold Comparison:**
   - Run retrieval smoke test at current threshold
   - Run at recommended threshold
   - Compare result quality

---

## 9. Rollback Plan

1. **Immediate Rollback:**
   ```bash
   rm scripts/eval_grounding.py
   rm -rf data/eval/
   ```

2. **No data cleanup needed** - evaluation is offline/additive

3. **Verification After Rollback:**
   ```bash
   ls scripts/eval_grounding.py  # Should not exist
   ```

---

## 10. Current → Target Alignment

| Aspect | Current State | This PRP Moves To | North Star Target |
|--------|---------------|-------------------|-------------------|
| Threshold tuning | Heuristic (0.6) | Data-driven recommendation | Auto-tuning per domain |
| Evaluation data | None | 50 labeled queries | 500+ with periodic refresh |
| Metrics tracking | Manual inspection | Scripted metrics | CI/CD metric gates |

**Gap Remaining:** Auto-tuning, larger eval set, CI integration

---

## 11. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Labels are biased | Medium | Medium | Include diverse query types in ground truth |
| Optimal threshold varies by domain | Medium | Low | Document as limitation; future: per-equipment thresholds |
| BAS-Ontology changes affect results | Low | Medium | Version-pin evaluation; re-run after ontology updates |

---

## 12. Docs Impact

After implementation, update these documents:

- [ ] **CONTEXT.md:** Add section on evaluation methodology under "Safe Extension Guide"
- [x] **STATE.md:** Add `scripts/eval_grounding.py` to file structure, document eval capability
- [ ] **README.md:** No change (internal tooling)
- [ ] **Diagrams:** No change

---

## Changelog

| Date | Author | Change |
|------|--------|--------|
| 2026-01-10 | Engineering | Initial draft |
