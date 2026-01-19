# DaemonIQ Context Contract

> **Version:** 1.0.0
> **Last Updated:** 2026-01-10
> **Scope:** Platform-wide invariants, contracts, and extension rules for DaemonIQ

---

## 1. System Purpose & Boundaries

### What DaemonIQ IS

DaemonIQ is a **BAS (Building Automation Systems) semantic knowledge platform** that provides:

1. **Canonical BAS Ontology Layer** - Haystack/Brick + Yorkland extensions as the authoritative source for concept types and relationships
2. **Grounding Layer** - Converts messy user language into stable ontology concepts with confidence scores and traceable evidence
3. **Metadata-Aware Retrieval** - Uses grounded concepts to filter and boost vector search results with explicit fallbacks
4. **Constrained Answer Generation** - LLM answers are constrained by ontology + retrieved evidence, with citations for factual claims
5. **Dual Frontend Architecture**:
   - **RAG UI** - Chat/search UX, citations, transparency views ("why this answer")
   - **Ontology UI** - Schema/topology/ontology explorer for learning and debugging

### What DaemonIQ is NOT

- NOT an autonomous agent that takes actions in customer environments
- NOT a reasoning system that bypasses grounding/retrieval/citations
- NOT a platform where UIs define semantics (UIs render/teach/inspect only)
- NOT a system that invents ontology terms or makes unsourced claims

### Boundary: This Repo (daemonIQ-rag)

This repository (`daemonIQ-rag`) is the **RAG service layer**. It:
- Owns document ingestion, chunking, embedding, and storage in Qdrant
- Owns query-time retrieval, reranking, and answer synthesis
- Depends on BAS-Ontology as an external grounding service
- Serves the RAG UI (chat/search endpoints)

---

## 2. Architecture Overview

### CURRENT STATE (As-Built)

Current wiring (ports, models, env vars) is tracked in [STATE.md](STATE.md).

See [diagrams/rag_architecture.mmd](diagrams/rag_architecture.mmd) and [diagrams/ontology_architecture.mmd](diagrams/ontology_architecture.mmd) for architecture visualizations.

**Current Flow (Phase 1A + 1B):**
1. **Ingest-time:** PDF -> chunks -> ground each chunk via BAS-Ontology -> embed -> store in Qdrant with metadata
2. **Query-time:** User query -> ground query -> (if confidence >= threshold) filtered retrieval + rerank -> (else) vanilla retrieval -> LLM answer with citations

### TARGET STATE (North Star)

1. **Ontology layer** is authoritative for all concept definitions and relationships
2. **Grounding** always precedes retrieval; explicit fallbacks (no magic bypass)
3. **Yorkland Extensions** become a versioned product ontology with provenance for each mapping
4. **Retrieval** becomes topology-aware (traversing equipment relationships)
5. **Answers** are strictly constrained: no invented terms, citations required
6. **UIs** remain visualization/inspection tools; they never encode semantics

### Migration Strategy

PRPs (Plan-Review-Propose documents) bridge CURRENT -> TARGET:
- Each PRP defines acceptance criteria, tests, and rollback plan
- PRPs explicitly state which STATE.md fields change
- Changes to CONTEXT.md invariants require elevated review

---

## 3. Component Responsibilities

### daemonIQ-rag (This Repo)

| Responsibility | Owns | Does NOT Own |
|----------------|------|--------------|
| Document ingestion | Chunking, embedding, Qdrant storage | PDF parsing library internals |
| Grounding integration | Calling BAS-Ontology, extracting payload | Ontology definitions |
| Retrieval | Vanilla + grounded modes, reranking | Vector similarity algorithm |
| Answer synthesis | LLM prompting, citation extraction | LLM weights/behavior |
| RAG API | /ingest, /chat, /retrieve endpoints | Frontend rendering |

### BAS-Ontology (External Dependency)

| Responsibility | Provides via API |
|----------------|------------------|
| Entity detection | POST /api/ground -> equipment_types, point_types, raw_tags |
| Ontology exploration | GET /ontology/*, GET /api/schema/*, GET /api/topology/* |
| Health check | GET /health |

**Schema Expectation (grounding.v1):** daemonIQ-rag expects BAS-Ontology `/api/ground` to return a shape like:
```json
{
  "equipment_types": [{"haystack_kind": "vav", "brick_class": "Variable_Air_Volume_Box", "confidence": 0.95}],
  "point_types": [{"haystack_tags": ["discharge", "air", "temp", "sensor"], "confidence": 0.9}],
  "raw_tags": ["air", "discharge", "temp", "vav"]
}
```

**Compatibility Note:** This is the observed current response shape. daemonIQ-rag must tolerate extra fields (forward compatibility) and missing optional fields (use defaults). If BAS-Ontology introduces breaking changes, coordinate via a versioned endpoint or migration PRP.

### Qdrant

| Responsibility | Configuration |
|----------------|---------------|
| Vector storage | Collection: `bas_docs`, dimension: 384, distance: Cosine |
| Payload filtering | Supports MatchAny on array fields |
| Persistence | Docker volume mounted |

### Yorkland Extensions (Future)

| Responsibility | Target State |
|----------------|--------------|
| Product ontology | Versioned graph of Yorkland products as first-class concepts |
| Ontology mappings | Each mapping has provenance (source doc URL, confidence) |
| Integration | Loaded by BAS-Ontology alongside Haystack/Brick |

### RAG UI (Future)

| Responsibility | Scope |
|----------------|-------|
| Chat interface | User query input, streaming response display |
| Citation display | Show source documents, page numbers, highlights |
| Transparency views | "Why this answer" - show grounding, filters applied, chunks retrieved |

### Ontology UI (External)

| Responsibility | Scope |
|----------------|-------|
| Schema browser | Explore Haystack/Brick hierarchies |
| Topology viewer | Visualize ASHRAE G36 patterns, equipment relationships |
| Educational layer | Help users understand BAS concepts |

---

## 4. Invariants (Hard Rules)

These rules are **non-negotiable**. Violating them requires a PRP with elevated review.

### INV-1: Separate Ingest-Time vs Query-Time Cognition

- **Ingest-time:** Extract and store stable metadata (grounding payload) once per chunk
- **Query-time:** Ground the query, apply filters/boosts, retrieve, synthesize
- **Rationale:** Ingest-time processing is expensive; query-time must be fast and consistent

### INV-2: Ontology Defines Semantics; Documents Are Evidence Only

- The ontology (Haystack/Brick/Yorkland) is the **single source of truth** for what concepts exist and how they relate
- Documents provide **evidence** for factual claims, not concept definitions
- The LLM must not invent new ontology terms

### INV-3: Grounding Precedes Filtered Retrieval

```
Query -> Ground -> Confidence Check
                      |
                      v
              >= threshold (0.6)?
                 /          \
               YES           NO
                |             |
                v             v
         Build Filter    Vanilla Retrieval
                |
                v
         Filtered Search
                |
                v
         Results > 0?
           /       \
         YES        NO
          |          |
          v          v
       Rerank    Vanilla Retrieval
          |
          v
       Top K
```

- **No silent bypass:** If grounding fails or returns low confidence, explicitly fall back to vanilla with logging
- **No magic:** Every decision point in the flow must be traceable

### INV-4: LLM Must Not Invent; Factual Claims Require Citations

- LLM prompts must include: "Answer ONLY using information from the context below"
- Every factual claim in the response should trace to a retrieved chunk
- If information is missing, the LLM must say so rather than hallucinate

### INV-5: UIs Render/Teach/Inspect; They Do Not Encode Semantics

- UIs visualize data from the backend; they do not define what concepts exist
- No hardcoded equipment types, point patterns, or ontology relationships in frontend code
- All semantic knowledge flows from BAS-Ontology

### INV-6: Data Contracts Are Explicit, Versioned, and Migrated Safely

- Schema changes to chunk metadata require a migration PRP
- New fields must have defined types, allowed values, and defaults
- Qdrant collection schema changes require reindexing plan

---

## 5. Data Contracts

### Chunk Metadata Schema (Qdrant Payload)

Every chunk stored in Qdrant MUST have these fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `source_id` | string | YES | Unique identifier for source document (e.g., hash or UUID) |
| `source_ref` | string | YES | Relative path or filename (portable, no absolute paths) |
| `page_label` | string | YES | Page number in source document |
| `_node_content` | string | YES | Chunk text content |
| `equip` | string[] | YES | Haystack equipment kinds (lowercase) |
| `brick_equip` | string[] | YES | Brick equipment classes (PascalCase) |
| `ptags` | string[] | YES | Point tag combinations (space-separated) |
| `raw` | string[] | YES | Raw normalized tags (lowercase, sorted) |
| `gconf` | float | YES | Average grounding confidence (0.0-1.0) |

**Optional Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `source_uri` | string | Full URI if document is web-accessible |

**Normalization Rules:**
- `source_ref`: relative path from DATA_DIR, or just filename; never absolute paths (security + portability)
- `equip`: lowercase, no spaces, from Haystack kinds vocabulary
- `brick_equip`: PascalCase with underscores, from Brick class hierarchy
- `ptags`: space-joined Haystack tags in canonical order (e.g., "discharge air temp sensor")
- `raw`: lowercase, alphabetically sorted, deduplicated
- `gconf`: 0.0 if no concepts grounded, otherwise average of all concept confidences

**Empty Defaults:**
- If grounding fails or returns nothing: `equip=[], brick_equip=[], ptags=[], raw=[], gconf=0.0`
- Empty arrays are valid; null is NOT valid

**Migration Note:** Legacy payloads may have `file_name` and `file_path` instead of `source_id`/`source_ref`. Code should tolerate both during transition.

### Filter Construction Contract

When building Qdrant filters from grounded query concepts:

```python
# OR semantics: match ANY condition
filter = Filter(should=[
    FieldCondition(key="equip", match=MatchAny(any=equip_list)),
    FieldCondition(key="brick_equip", match=MatchAny(any=brick_equip_list)),
    FieldCondition(key="ptags", match=MatchAny(any=ptags_list))
])
```

**Filter Decision Rules:**
1. If `gconf < GROUNDED_MIN_CONF` (default 0.6) -> skip filter, use vanilla
2. If only generic equipment (actuator, meter, sensor, controller) -> skip filter, use vanilla
3. If filter returns 0 results -> fall back to vanilla

### Reranking Contract

When reranking filtered results:

| Overlap Type | Boost Multiplier |
|--------------|------------------|
| `equip` match | 1.5x |
| `brick_equip` match | 1.3x |
| `ptags` match | 1.2x |

Boosts are multiplicative: `equip + brick_equip + ptags = 1.5 * 1.3 * 1.2 = 2.34x`

---

## 6. Query Flow Decision Logic

```
USER QUERY
    |
    v
[Ground Query via BAS-Ontology /api/ground]
    |
    v
gconf >= GROUNDED_MIN_CONF (0.6)?
    |
   NO -----> [VANILLA RETRIEVAL] --> top_k results --> [LLM SYNTHESIS] --> answer + citations
    |
   YES
    |
    v
Has high-value equipment? (vav, ahu, fcu, rtu, chiller, boiler, pump, fan)
    |
   NO (only generic) -----> [VANILLA RETRIEVAL]
    |
   YES
    |
    v
[BUILD QDRANT FILTER] (OR on equip/brick_equip/ptags)
    |
    v
[FILTERED SEARCH] limit = top_k * 4
    |
    v
Results > 0?
    |
   NO -----> [VANILLA RETRIEVAL]
    |
   YES
    |
    v
[RERANK BY OVERLAP] (equip 1.5x, brick 1.3x, ptags 1.2x)
    |
    v
[SELECT TOP K]
    |
    v
[LLM SYNTHESIS] with BAS-specific prompt
    |
    v
ANSWER + CITATIONS (source file, page)
```

---

## 7. Failure Modes & Fallbacks

| Failure | Detection | Fallback | Logging |
|---------|-----------|----------|---------|
| BAS-Ontology down | ConnectionError on /api/ground | Skip grounding, vanilla retrieval | WARNING: "Cannot connect to BAS-Ontology" |
| Grounding timeout | 2s timeout exceeded | Return empty payload, vanilla retrieval | WARNING: "Grounding API timeout" |
| Low confidence | gconf < 0.6 | Vanilla retrieval | INFO: "Confidence X < threshold, fallback" |
| Filter too restrictive | 0 results from filtered search | Vanilla retrieval | INFO: "No results with filter, fallback" |
| Qdrant down | ConnectionError on query | HTTP 503 to client | ERROR: "Qdrant connection failed" |
| Ollama down | Timeout on LLM call | HTTP 504 to client | ERROR: "LLM timeout" |
| Embeddings fail | Exception in FastEmbed | HTTP 500 to client | ERROR: "Embedding generation failed" |

**Principle:** Degrade gracefully to less-precise but still-useful results. Never return errors when vanilla retrieval could succeed.

---

## 8. Safe Extension Guide

### Adding a New Metadata Field

1. **Create PRP** with:
   - Field name, type, description, allowed values
   - Migration strategy for existing chunks (reindex or backfill?)
   - Impact on filters, reranking, UI

2. **Update Data Contract** in this document

3. **Implement** in order:
   - Add field to grounding payload extraction
   - Update filter construction if field is filterable
   - Update reranking if field affects ranking
   - Add to verification scripts

4. **Test** with:
   - Unit tests for extraction
   - Integration tests for retrieval with new field
   - Verify Qdrant payload contains field

5. **Document** in STATE.md

### Changing Retrieval/Reranking Logic

1. **Create PRP** with:
   - Current behavior vs proposed behavior
   - Expected impact on precision/recall
   - Rollback plan

2. **Implement behind feature flag**:
   - Add env var (e.g., `NEW_RERANK_MODE=0|1`)
   - Default to existing behavior

3. **A/B test** (optional):
   - Log retrieval metrics for both modes
   - Compare precision on evaluation queries

4. **Graduate** after validation:
   - Set new behavior as default
   - Update STATE.md

### Adding UI Transparency Views

1. **Principle:** UI shows what backend computed; it doesn't compute itself

2. **Backend must expose:**
   - Grounding result for query (concepts, confidence)
   - Filter applied (or "vanilla" indicator)
   - Retrieved chunks with scores (before and after reranking)
   - Which chunks were used in final answer

3. **UI renders:**
   - "Grounded to: VAV, discharge air temp sensor" badge
   - "Filtered by: equipment=vav" indicator
   - Expandable source list with relevance scores

### Evolving Yorkland Extensions

1. **Version the extension file** (e.g., `yorkland_ext_v1.2.json`)

2. **Include provenance** for each mapping:
   ```json
   {
     "product_id": "YLD-VAV-100",
     "maps_to": {"haystack_kind": "vav", "brick_class": "Variable_Air_Volume_Box"},
     "provenance": {
       "source_url": "https://yorkland.com/products/YLD-VAV-100",
       "extraction_date": "2026-01-10",
       "confidence": 0.95
     }
   }
   ```

3. **Load in BAS-Ontology**, not in this repo

4. **Test mapping coverage** via automated checks

---

## 9. Do/Don't List for Coding Agents

### DO

- Read CONTEXT.md before making architectural changes
- Create a PRP for any change affecting data contracts or invariants
- Fall back to vanilla retrieval on any grounding/filter failure
- Log all decision points (grounding result, filter applied, fallback reason)
- Test with BAS-specific queries (VAV, AHU, chiller, etc.)
- Keep UIs "dumb" - they render backend data, nothing more
- Cite sources for every factual claim in LLM output
- Use type hints and Pydantic models for data contracts
- Run existing tests before committing

### DON'T

- Add equipment types or point patterns to UI code
- Silently skip grounding without logging
- Invent ontology terms in LLM prompts
- Hardcode confidence thresholds outside .env configuration
- Change Qdrant schema without a migration PRP
- Push to main without passing tests
- Merge PRPs without acceptance criteria being met
- Add "magic" retrieval bypasses that skip grounding
- Store null values in array fields (use empty arrays)

---

## 10. Architecture Diagrams

The following Mermaid diagrams represent the **CURRENT STATE** of the system. They are snapshots that may lag behind the latest implementation.

- **[diagrams/rag_architecture.mmd](diagrams/rag_architecture.mmd)** - RAG service architecture (ingest + query flow)
- **[diagrams/ontology_architecture.mmd](diagrams/ontology_architecture.mmd)** - BAS-Ontology service architecture

When reading these diagrams:
- YELLOW boxes = data/documents
- PURPLE boxes = services/processes
- PINK boxes = external systems
- Diamond shapes = decision points
- Arrows show data flow direction

---

## 11. Open Questions / Needs Confirmation

1. **Yorkland Extensions versioning:** What's the release cadence? How do we handle breaking changes?

2. **RAG UI framework:** React/Vite as shown in ontology diagram, or different stack for RAG UI?

3. **Topology-aware retrieval (Phase 2):** How do hypernodes integrate with current chunk retrieval?

4. **Multi-tenant support:** Is collection-per-tenant the model, or namespace within collection?

5. **Evaluation metrics:** What precision/recall targets define "good enough" grounded retrieval?

6. **LLM swap:** Is qwen2.5:0.5b permanent, or placeholder for larger model in production?

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-01-10 | Initial Context Contract based on Phase 1A/1B implementation |
