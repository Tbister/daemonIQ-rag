# Feature Request Intake

> Fill this template to request a new feature or change. This is the "front door" into the PRP workflow.

---

## Request Title

Add "Why This Answer" Transparency View to RAG API

---

## Requester

- **Name:** Product Team
- **Date:** 2026-01-10
- **Priority:** Medium

---

## Problem Statement

Users asking BAS questions can't see why the system returned a particular answer. They don't know which documents were retrieved, what grounding concepts were detected, or how confident the system is. This makes it hard to trust or debug incorrect answers.

---

## Proposed Solution (Optional)

Add a `/chat-debug` endpoint (or flag on `/chat`) that returns the full retrieval context alongside the answer:
- Grounded concepts from query
- Filter applied (or "vanilla" indicator)
- Retrieved chunks with scores
- Which chunks the LLM actually used

---

## User Story

As a **BAS technician**, I want to **see why the system gave me this answer** so that **I can verify it's based on the right documents and not hallucinated**.

---

## Acceptance Criteria (Draft)

1. [x] API returns grounding result (concepts + confidence) in response
2. [ ] API returns list of retrieved chunks with relevance scores
3. [ ] API indicates whether grounded or vanilla retrieval was used
4. [ ] Response includes source document names and page numbers
5. [ ] No increase in latency for users who don't need debug info

---

## Constraints / Non-Goals

**Must:**
- Work with existing `/chat` endpoint (flag-based, not separate endpoint)
- Return structured JSON that UI can render

**Must NOT:**
- Slow down normal chat responses
- Expose internal system paths or sensitive config

**Out of Scope:**
- UI rendering (that's a separate frontend ticket)
- Modifying the answer generation logic

---

## Relevant Context

**Related Files/Components:**
- `app/main.py` - `/chat` endpoint
- `app/grounding.py` - `ground_query()` function
- `context/CONTEXT.md` - Section 8: "Adding UI Transparency Views"

**Related PRPs:**
- None yet

**External Dependencies:**
- None (uses existing grounding and retrieval)

---

## Questions for Engineering

1. Should this be a query param (`?debug=true`) or separate endpoint (`/chat-debug`)?
2. How much detail in chunk text - full text or truncated preview?
3. Should we include the raw BAS-Ontology grounding response or just extracted concepts?

---

## Engineering Review

*To be filled by engineering after review*

**Reviewer:** Engineering Lead
**Review Date:** 2026-01-10
**Decision:** Accept
**Assigned PRP:** `PRPs/transparency_debug_response.md`
**Notes:**
- Recommend query param approach (`?debug=1`) for simplicity
- Truncate chunk text to 200 chars in debug response
- Include extracted concepts only, not raw API response (per INV-5: UI renders, doesn't interpret)
- Estimate: 1-2 days implementation
