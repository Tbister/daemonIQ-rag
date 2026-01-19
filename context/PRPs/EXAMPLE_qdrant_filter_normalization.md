# PRP: Qdrant Filter Normalization

> **Status:** Draft
> **Author:** Engineering Team
> **Created:** 2026-01-10
> **Target Phase:** Post-1B Enhancement

---

## 1. Objective

Normalize equipment type values in Qdrant filters to handle case variations and common aliases. Currently, a query grounded to "VAV" won't match chunks tagged with "vav" if case differs.

**Success Metric:** 100% of filter matches are case-insensitive; "VAV", "Vav", "vav" all match chunks tagged with any variant.

---

## 2. Current State

**Relevant Files:**
- `app/main.py:130-187` - `build_grounded_filter()` function
- `app/grounding.py:70-80` - Equipment extraction (preserves case from API)
- `context/CONTEXT.md` - Data contract specifies lowercase for `equip`

**Limitations Addressed:**
1. BAS-Ontology may return mixed-case equipment names
2. Historical chunks may have inconsistent casing
3. MatchAny is case-sensitive

---

## 3. Proposed Change

Add normalization layer that:
1. Lowercases all `equip` values before filter construction
2. Adds alias expansion for common variations (e.g., "VAV" -> ["vav", "variable-air-volume"])
3. Logs normalized values for debugging

### Architecture Impact

```
Current:
  ground_query() -> {"equip": ["VAV"]} -> build_filter(equip=["VAV"]) -> NO MATCH (chunks have "vav")

Proposed:
  ground_query() -> {"equip": ["VAV"]}
                          |
                          v
                   normalize_concepts()
                          |
                          v
                   {"equip": ["vav"]}
                          |
                          v
                   build_filter(equip=["vav"]) -> MATCH
```

### Data Contract Changes

| Field | Before | After | Migration |
|-------|--------|-------|-----------|
| `equip` | string[] (mixed case) | string[] (lowercase) | Reindex with `force_rebuild=true` |

**Note:** This enforces the existing contract in CONTEXT.md which specifies lowercase.

### API Changes

| Endpoint | Change |
|----------|--------|
| N/A | No API changes (internal normalization) |

---

## 4. Constraints

- [x] Must not violate INV-6 (data contracts explicit and versioned)
- [x] Must maintain backward compatibility with existing chunks
- [x] Must not increase query latency by more than 5ms
- [x] Must handle empty arrays gracefully

---

## 5. Acceptance Criteria

- [ ] **AC-1:** Query with "VAV" matches chunks tagged "vav"
  - Test: `curl -X POST "${RAG_URL:-http://localhost:8000}/retrieve" -H 'Content-Type: application/json' -d '{"q":"VAV discharge temperature"}' | jq '.results[0].metadata.equip'`
  - Expected: Contains "vav"

- [ ] **AC-2:** Query with "vav" still works
  - Test: `curl -X POST "${RAG_URL:-http://localhost:8000}/retrieve" -H 'Content-Type: application/json' -d '{"q":"vav discharge temperature"}' | jq '.results[0].metadata.equip'`
  - Expected: Contains "vav"

- [ ] **AC-3:** Normalization logged when enabled
  - Test: Set `LOG_GROUNDED_RETRIEVAL=1`, run query, check logs
  - Expected: "Normalized equip: ['VAV'] -> ['vav']"

- [ ] **AC-4:** Empty arrays handled without error
  - Test: Query with no equipment concepts
  - Expected: No errors, falls back to vanilla

---

## 6. Impacted Files

| File | Change Type | Description |
|------|-------------|-------------|
| `app/main.py` | Modify | Add `normalize_concepts()` function, call before `build_grounded_filter()` |
| `app/grounding.py` | Modify | Normalize at extraction time (alternative approach) |
| `tests/test_normalization.py` | Add | Unit tests for normalization |
| `context/STATE.md` | Update | Document normalization behavior |

---

## 7. Step Plan

### Step 1: Add Normalization Function
**Files:** `app/main.py`
**Actions:**
1. Add `normalize_concepts(concepts: Dict) -> Dict` function
2. Lowercase all `equip` values
3. Lowercase all `brick_equip` values (optional, PascalCase may be intentional)
4. Add logging when normalization changes values

```python
def normalize_concepts(concepts: Dict[str, any]) -> Dict[str, any]:
    """Normalize grounding concepts for consistent filtering."""
    normalized = concepts.copy()

    # Lowercase equipment types
    if "equip" in normalized:
        original = normalized["equip"]
        normalized["equip"] = [e.lower() for e in original]
        if LOG_GROUNDED_RETRIEVAL and original != normalized["equip"]:
            logger.info(f"  Normalized equip: {original} -> {normalized['equip']}")

    return normalized
```

**Validation:** Unit test with mixed-case input

### Step 2: Integrate into Retrieval Flow
**Files:** `app/main.py`
**Actions:**
1. Call `normalize_concepts()` after `ground_query()` in `grounded_retrieve()`
2. Pass normalized concepts to `build_grounded_filter()` and `rerank_by_overlap()`

**Validation:** End-to-end test with "VAV" query

### Step 3: Add Unit Tests
**Files:** `tests/test_normalization.py`
**Actions:**
1. Test lowercase conversion
2. Test empty array handling
3. Test no-change case (already lowercase)

**Validation:** `pytest tests/test_normalization.py -v`

---

## 8. Validation Steps

1. **Unit Tests:**
   ```bash
   pytest tests/test_normalization.py -v
   ```
   Expected: All pass

2. **Integration Test:**
   ```bash
   # Query with uppercase
   curl -X POST "${RAG_URL:-http://localhost:8000}/retrieve" \
     -H 'Content-Type: application/json' \
     -d '{"q":"VAV discharge temperature","k":4}' | jq '.results[0].metadata.equip'
   ```
   Expected: Contains "vav"

3. **Regression Check:**
   ```bash
   python scripts/smoke_grounded_query.py
   ```
   Expected: All queries still return relevant results

4. **Manual Verification:**
   - [x] Query "VAV" returns VAV-tagged chunks
   - [x] Query "chiller" returns chiller-tagged chunks
   - [x] Logs show normalization when applicable

---

## 9. Rollback Plan

1. **Immediate Rollback:**
   ```bash
   # Remove normalize_concepts() call from grounded_retrieve()
   git revert HEAD
   ```

2. **No data cleanup needed** - normalization is query-time only

3. **Verification After Rollback:**
   ```bash
   # Confirm old behavior (case-sensitive)
   curl -X POST "${RAG_URL:-http://localhost:8000}/retrieve" \
     -H 'Content-Type: application/json' -d '{"q":"VAV test"}' | jq '.mode'
   # Should work but may miss some matches
   ```

---

## 10. Current → Target Alignment

| Aspect | Current State | This PRP Moves To | North Star Target |
|--------|---------------|-------------------|-------------------|
| Case handling | Case-sensitive filters | Case-insensitive | Case-insensitive + alias expansion |
| Alias expansion | None | None (future PRP) | "VAV" -> ["vav", "variable-air-volume-box"] |
| Contract enforcement | Documented but not enforced | Enforced at query time | Enforced at ingest + query time |

**Gap Remaining:** Alias expansion, ingest-time normalization

---

## 11. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Brick classes need PascalCase | Medium | Low | Don't normalize brick_equip (intentionally different) |
| Performance overhead | Low | Low | String operations are O(n) on small arrays |
| Breaks existing filter behavior | Low | Medium | Normalization only makes matches MORE permissive |

---

## 12. Docs Impact

After implementation, update these documents:

- [ ] **CONTEXT.md:** Clarify that normalization is enforced at query-time
- [x] **STATE.md:** Document normalization behavior, update version
- [ ] **README.md:** No change (internal behavior)
- [ ] **Diagrams:** No change

---

## Changelog

| Date | Author | Change |
|------|--------|--------|
| 2026-01-10 | Engineering | Initial draft |
