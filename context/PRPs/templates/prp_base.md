# PRP: [Short Title]

> **Status:** Draft | In Review | Approved | Implemented | Rejected
> **Author:** [Name]
> **Created:** [YYYY-MM-DD]
> **Target Phase:** [Phase number or "Standalone"]

---

## 1. Objective

[2-3 sentences describing what this PRP accomplishes and why it matters]

**Success Metric:** [Quantifiable outcome, e.g., "Precision on VAV queries improves from 60% to 80%"]

---

## 2. Current State

[Describe what exists today, referencing STATE.md and diagrams]

**Relevant Files:**
- `app/file.py:123` - [what it does]
- `context/STATE.md` - [current config]

**Limitations Addressed:**
1. [Limitation 1]
2. [Limitation 2]

---

## 3. Proposed Change

[Detailed description of what will change]

### Architecture Impact

```
[ASCII or Mermaid diagram showing change, if applicable]
```

### Data Contract Changes

| Field | Before | After | Migration |
|-------|--------|-------|-----------|
| [field] | [type/value] | [type/value] | [strategy] |

### API Changes

| Endpoint | Change |
|----------|--------|
| [endpoint] | [added/modified/removed] |

---

## 4. Constraints

- [ ] Must not violate [INV-X from CONTEXT.md]
- [ ] Must maintain backward compatibility with [component]
- [ ] Must not increase query latency by more than [X]ms
- [ ] Must work when [external service] is unavailable

---

## 5. Acceptance Criteria

Each criterion must be testable. Use checkbox format.

- [ ] **AC-1:** [Specific, measurable criterion]
  - Test: `[command or test name]`
  - Expected: [outcome]

- [ ] **AC-2:** [Specific, measurable criterion]
  - Test: `[command or test name]`
  - Expected: [outcome]

- [ ] **AC-3:** [Specific, measurable criterion]
  - Test: `[command or test name]`
  - Expected: [outcome]

---

## 6. Impacted Files

| File | Change Type | Description |
|------|-------------|-------------|
| `app/main.py` | Modify | [what changes] |
| `app/new_module.py` | Add | [purpose] |
| `context/STATE.md` | Update | [what changes] |

---

## 7. Step Plan

### Step 1: [Title]
**Files:** `[file1]`, `[file2]`
**Actions:**
1. [Action 1]
2. [Action 2]

**Validation:** [How to verify this step succeeded]

### Step 2: [Title]
**Files:** `[file1]`
**Actions:**
1. [Action 1]

**Validation:** [How to verify]

### Step 3: Integration Test
**Run:** `[test command]`
**Expected:** [outcome]

---

## 8. Validation Steps

After all implementation steps:

1. **Unit Tests:**
   ```bash
   pytest tests/test_[feature].py -v
   ```
   Expected: All pass

2. **Integration Test:**
   ```bash
   # Use env vars for service URLs (see STATE.md for defaults)
   curl -X POST "${RAG_URL:-http://localhost:8000}/[endpoint]" \
     -H 'Content-Type: application/json' -d '[payload]'
   ```
   Expected: [specific output]

3. **Regression Check:**
   ```bash
   pytest tests/ -v
   ```
   Expected: No existing tests broken

4. **Manual Verification:**
   - [ ] [Manual check 1]
   - [ ] [Manual check 2]

---

## 9. Rollback Plan

If issues are discovered post-implementation:

1. **Immediate Rollback:**
   ```bash
   [command to revert, e.g., git revert or env var change]
   ```

2. **Data Cleanup (if applicable):**
   ```bash
   [command to clean up any persisted changes]
   ```

3. **Verification After Rollback:**
   ```bash
   [command to verify system is back to previous state]
   ```

---

## 10. Current → Target Alignment

| Aspect | Current State | This PRP Moves To | North Star Target |
|--------|---------------|-------------------|-------------------|
| [Aspect 1] | [Current] | [After PRP] | [Ultimate goal] |
| [Aspect 2] | [Current] | [After PRP] | [Ultimate goal] |

**Gap Remaining:** [What still needs to be done after this PRP]

---

## 11. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| [Risk 1] | Low/Med/High | Low/Med/High | [How to prevent/handle] |
| [Risk 2] | Low/Med/High | Low/Med/High | [How to prevent/handle] |

---

## 12. Docs Impact

### STATE.md Update Checklist

**You MUST update STATE.md if this PRP changes any of:**
- [ ] Service ports or URLs
- [ ] Model names or versions (embeddings, LLM, etc.)
- [ ] Environment variables (added, removed, or default changed)
- [ ] API endpoints (added, removed, or signature changed)
- [ ] External dependencies (new service, version bump)
- [ ] Qdrant collection name or schema
- [ ] File structure (new directories, moved files)

**Tip:** Run `python scripts/state_snapshot.py` to generate a current snapshot for copy-paste.

### Other Docs

- [ ] **CONTEXT.md:** Only if invariants or data contracts change
- [ ] **README.md:** Only if user-facing behavior changes
- [ ] **Diagrams:** Only if architecture flow changes

---

## Changelog

| Date | Author | Change |
|------|--------|--------|
| [date] | [name] | Initial draft |
