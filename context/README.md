# DaemonIQ Governance Hub

This folder contains the **Context Engineering** framework for DaemonIQ - a structured approach to managing architectural decisions, data contracts, and feature development.

---

## Quick Links

| Document | Purpose |
|----------|---------|
| [CONTEXT.md](CONTEXT.md) | **System invariants, data contracts, extension rules** - The "constitution" |
| [STATE.md](STATE.md) | **Current implementation snapshot** - What exists today |
| [INITIAL.md](INITIAL.md) | **Feature request template** - Front door for new work |
| [PRPs/](PRPs/) | **Plan-Review-Propose documents** - Detailed implementation plans |
| [diagrams/](diagrams/) | **Architecture diagrams** - Mermaid source files |

---

## Understanding Current vs Target State

### Key Distinction

| Concept | Source of Truth | Description |
|---------|-----------------|-------------|
| **CURRENT STATE** | `STATE.md` + `diagrams/` | What's actually built and running |
| **TARGET STATE** | `CONTEXT.md` (North Star) | Where we're heading |
| **MIGRATION** | `PRPs/` | How we get from Current to Target |

### When Reading Documents

- **Diagrams (`diagrams/*.mmd`)** represent the CURRENT STATE at time of last update. They may lag behind the code.
- **CONTEXT.md invariants** are aspirational but enforced - code should comply.
- **STATE.md** is volatile - update it whenever implementation changes.

### Conflict Resolution

If STATE.md contradicts CONTEXT.md:
- **CONTEXT.md wins** on invariants and data contracts (the rules)
- **STATE.md wins** on current wiring, ports, versions (the facts)

Example: If STATE.md says threshold is 0.5 but CONTEXT.md says 0.6, the contract (CONTEXT.md) is correct and STATE.md should be fixed.

---

## Workflow: From Idea to Implementation

```
┌─────────────────────────────────────────────────────────────────┐
│  1. INTAKE                                                      │
│     Fill context/INITIAL.md with your feature request           │
│     Save as context/intake/YYYY-MM-DD_short_name.md             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. ENGINEERING REVIEW                                          │
│     - Review against CONTEXT.md constraints                     │
│     - Check for conflicts with invariants                       │
│     - Accept / Needs Clarification / Reject                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. CREATE PRP                                                  │
│     Copy PRPs/templates/prp_base.md                             │
│     Fill all sections                                           │
│     Save as PRPs/YYYY-MM-DD_short_name.md                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  4. PRP REVIEW                                                  │
│     - Verify acceptance criteria are testable                   │
│     - Verify rollback plan is viable                            │
│     - Verify CONTEXT.md impact is documented                    │
│     - Approve or request changes                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  5. IMPLEMENT                                                   │
│     Follow PRP step plan                                        │
│     Run validation at each step                                 │
│     Update tests                                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  6. VERIFY                                                      │
│     Run all acceptance criteria tests                           │
│     Run regression tests                                        │
│     Manual verification if required                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  7. UPDATE DOCS                                                 │
│     Update STATE.md with new wiring/config                      │
│     Update CONTEXT.md if contracts changed                      │
│     Update diagrams if architecture changed                     │
│     Mark PRP as "Implemented"                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## For Coding Agents (AI Assistants)

### Before Starting Work

1. **Read `CONTEXT.md`** - Understand invariants and contracts
2. **Read `STATE.md`** - Understand current implementation
3. **Check for existing PRPs** - Don't duplicate work

### When Implementing Features

1. **Create or follow a PRP** for non-trivial changes
2. **Check invariants** - Especially INV-1 through INV-6
3. **Update tests** - Every change needs validation
4. **Update docs** - STATE.md at minimum

### Guardrails (Hard Rules)

- **Never change architecture without a PRP**
- **Never weaken citations requirement** (INV-4)
- **Never encode semantics in UI code** (INV-5)
- **Never change metadata schema without migration plan** (INV-6)
- **Never skip grounding without explicit fallback logging** (INV-3)

### Quick Reference: Do/Don't

| DO | DON'T |
|----|-------|
| Read CONTEXT.md before architectural changes | Add equipment types to UI code |
| Create PRP for data contract changes | Silently skip grounding |
| Fall back to vanilla on any failure | Invent ontology terms in prompts |
| Log all decision points | Hardcode thresholds outside .env |
| Test with BAS-specific queries | Change Qdrant schema without PRP |

---

## File Structure

```
context/
├── README.md              # This file - how to use the hub
├── CONTEXT.md             # System invariants & contracts
├── STATE.md               # Current implementation snapshot
├── INITIAL.md             # Blank feature request template
├── INITIAL_EXAMPLE.md     # Filled example request
├── diagrams/
│   ├── rag_architecture.mmd       # RAG service flow (Mermaid)
│   └── ontology_architecture.mmd  # BAS-Ontology service (Mermaid)
├── PRPs/
│   ├── templates/
│   │   └── prp_base.md            # PRP template
│   ├── EXAMPLE_grounding_confidence_eval.md
│   └── EXAMPLE_qdrant_filter_normalization.md
└── intake/                # (Optional) Submitted feature requests
```

---

## Updating Diagrams

The Mermaid diagrams in `diagrams/` are source-of-truth for visual architecture. To update:

1. Edit the `.mmd` file directly
2. Preview using Mermaid Live Editor (https://mermaid.live) or VS Code extension
3. Commit the change
4. Note the update in STATE.md

**Convention:**
- YELLOW (`#fffacd`) = Data/documents
- PURPLE (`#e6e6fa`) = Services/processes
- PINK (`#ffb6c1`) = External systems
- Diamonds = Decision points

---

## PRP Lifecycle

```
Draft → In Review → Approved → Implemented → (Rejected)
                         ↓
                    Superseded (by newer PRP)
```

**Status Definitions:**
- **Draft:** Author is still writing
- **In Review:** Ready for engineering review
- **Approved:** Ready to implement
- **Implemented:** Code merged, docs updated
- **Rejected:** Won't implement (with documented reason)
- **Superseded:** Replaced by a newer PRP

---

## STATE.md Update Triggers

**Update STATE.md whenever any of these change:**

| Trigger | Example |
|---------|---------|
| Service ports | RAG API moves from 8000 to 8080 |
| Model versions | Embeddings change from bge-small to bge-base |
| Environment variables | New `GROUNDED_RERANK_BOOST` added |
| API endpoints | New `/ground` endpoint added |
| External dependencies | BAS-Ontology version bump |
| Qdrant collection | Collection renamed or schema changed |
| File structure | New `app/reranker.py` module added |

**Easy update workflow:**
```bash
python scripts/state_snapshot.py  # Prints current wiring
# Copy relevant sections into STATE.md
# Update "Last Updated" date
```

---

## FAQ

**Q: When do I need a PRP?**
A: For any change that affects data contracts, adds/removes API endpoints, changes retrieval logic, or modifies invariants.

**Q: Can I skip the PRP for small fixes?**
A: Bug fixes and typo corrections don't need PRPs. If you're adding new behavior or changing contracts, you need one.

**Q: Who approves PRPs?**
A: Engineering lead or designated reviewer. The approval is recorded in the PRP document.

**Q: What if I discover issues during implementation?**
A: Update the PRP with findings, re-review if scope changed significantly, or create a follow-up PRP.

**Q: How do I update CONTEXT.md?**
A: Create a PRP specifically for the contract change. CONTEXT.md changes require elevated review since they affect all future work.
