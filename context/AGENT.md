# DaemonIQ-rag — Agent Notes (short)

Read first:
- [CONTEXT.md](CONTEXT.md) (invariants + data contracts)
- [STATE.md](STATE.md) (current wiring: URLs/ports/models/env)

Guardrails:
- No architecture or retrieval-policy changes without a PRP (`PRPs/`).
- Don't weaken citation requirements: factual claims must cite retrieved chunks.
- Don't encode semantics in UI code; semantics come from BAS-Ontology.
- Don't change Qdrant payload schema without versioning + a migration PRP.

Rule of thumb:
- PRP for decisions (schemas, thresholds, retrieval/rerank, APIs). No PRP for chores.
