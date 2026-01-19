# DaemonIQ Current State

> **Last Updated:** 2026-01-10
> **Phase:** 1B Complete (Query-Time Steering)
> **Next Milestone:** Phase 2 (Hypergraph Construction)

This document captures the **current implementation state**. For invariants and contracts, see [CONTEXT.md](CONTEXT.md).

**Updating this file:** Run `python scripts/state_snapshot.py` to generate a fresh snapshot, then copy relevant sections here.

---

## Services & Ports

| Service | Port | Status | Notes |
|---------|------|--------|-------|
| daemonIQ-rag API | 8000 | Running | FastAPI, uvicorn |
| BAS-Ontology | 8001 | External | Must start separately |
| Qdrant | 6333 | Running | Docker container |
| Ollama | 11434 | Running | Local, `brew install ollama` |

## Current Models & Versions

| Component | Model/Version | Notes |
|-----------|---------------|-------|
| Embeddings | `BAAI/bge-small-en-v1.5` | 384 dimensions, via FastEmbed |
| LLM | `qwen2.5:0.5b` | Fast (1-3s), via Ollama |
| Vector DB | Qdrant (latest Docker) | Collection: `bas_docs` |
| Chunking | SentenceSplitter | 800 tokens, 200 overlap |

## Environment Variables

```bash
# Core
DATA_DIR=../data                    # PDF/TXT/MD source directory
QDRANT_COLLECTION=bas_docs          # Qdrant collection name
QDRANT_URL=http://localhost:6333    # Qdrant endpoint
OLLAMA_MODEL=qwen2.5:0.5b           # LLM model name

# Grounding (Phase 1A)
BAS_ONTOLOGY_URL=http://localhost:8001  # Grounding service

# Retrieval (Phase 1B)
RETRIEVAL_MODE=vanilla              # "vanilla" | "grounded"
GROUNDED_MIN_CONF=0.6               # Confidence threshold
GROUNDED_LIMIT_MULT=4               # Retrieve limit multiplier
LOG_GROUNDED_RETRIEVAL=0            # Debug logging (0|1)
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/test-ollama` | GET | Test Ollama connection |
| `/ingest` | POST | Ingest documents from DATA_DIR |
| `/retrieve` | POST | Retrieve chunks (no LLM) |
| `/chat` | POST | Full RAG (retrieve + LLM) |
| `/chat-stream` | POST | Streaming RAG response |

## Current Data State

| Metric | Value | As Of |
|--------|-------|-------|
| Documents indexed | 26 PDFs | 2026-01-08 |
| Total chunks | 2,975 | 2026-01-08 |
| Chunks with grounding | 1,747 (58.7%) | 2026-01-08 |
| Qdrant vectors | 2,048+ | 2026-01-08 |

## File Structure (This Repo)

```
daemonIQ-rag/
├── app/
│   ├── main.py           # FastAPI app, endpoints, retrieval logic
│   └── grounding.py      # BAS-Ontology integration
├── data/                 # Source documents (PDFs)
├── scripts/
│   ├── state_snapshot.py           # Generate STATE.md snapshot
│   ├── verify_qdrant_payload.py    # Phase 1A verification
│   └── smoke_grounded_query.py     # Phase 1B smoke test
├── tests/
│   └── test_fix.sh       # Test runner
├── context/              # Governance hub (this folder)
│   └── AGENT.md          # Agent entrypoint (short guardrails)
├── outputs/              # Analysis outputs
├── .env                  # Environment config
├── requirements.txt      # Python dependencies
├── Makefile             # Build/run commands
└── README.md            # User-facing docs
```

## Implementation Phases

| Phase | Status | Summary |
|-------|--------|---------|
| 0 | Complete | OG-RAG fit assessment |
| 1A | Complete | Ingest-time grounding (chunk metadata) |
| 1B | Complete | Query-time steering (filter + rerank) |
| 2 | Not Started | Hypergraph construction |

## Known Limitations

1. **Vanilla mode default:** `RETRIEVAL_MODE=vanilla` - grounded mode must be explicitly enabled
2. **No persistence for grounding cache:** Each query re-calls BAS-Ontology
3. **Generic concept filtering:** "actuator", "meter", "sensor", "controller" trigger fallback
4. **No multi-tenant:** Single collection serves all documents
5. **No RAG UI:** API-only, no chat frontend in this repo

## Dependencies on External Services

### BAS-Ontology (Required for Grounding)

- **Health check:** `curl http://localhost:8001/health`
- **Grounding API:** `POST /api/ground` with `{"query": "..."}`
- **Startup:** `cd /path/to/BAS-Ontology && BAS_PORT=8001 ./start.sh`
- **If unavailable:** Grounding skipped, vanilla retrieval only

### Qdrant (Required)

- **Startup:** `make qdrant-up` or `docker run -p 6333:6333 qdrant/qdrant`
- **Collection:** Created automatically on first `/ingest`
- **If unavailable:** All endpoints return 5xx errors

### Ollama (Required for /chat)

- **Startup:** `ollama serve` (runs on :11434)
- **Model pull:** `ollama pull qwen2.5:0.5b`
- **If unavailable:** `/chat` times out, `/retrieve` still works

## Diagrams

- [diagrams/rag_architecture.mmd](diagrams/rag_architecture.mmd) - RAG service flow
- [diagrams/ontology_architecture.mmd](diagrams/ontology_architecture.mmd) - BAS-Ontology service

These represent the current implementation as of the last diagram update. Code may have evolved since.

---

## Conflict Resolution

If STATE.md conflicts with CONTEXT.md:
- **CONTEXT.md wins** on invariants and data contracts
- **STATE.md wins** on current wiring, ports, env vars

Example: If STATE.md says `GROUNDED_MIN_CONF=0.5` but CONTEXT.md says threshold is 0.6, the contract (CONTEXT.md) is correct and STATE.md should be updated.

---

## Update Log

| Date | Change |
|------|--------|
| 2026-01-10 | Initial STATE.md from Phase 1A/1B summaries |
