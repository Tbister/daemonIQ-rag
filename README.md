# RAG Demo (FastAPI + LlamaIndex + Qdrant + Ollama)

Local RAG,  No paid APIs.

## Stack
- Vector DB: Qdrant (Docker)
- Embeddings: FastEmbed `BAAI/bge-small-en-v1.5` (384‑d)
- LLM: Ollama (e.g., `llama3.1` on Apple Silicon)
- Orchestrator/API: LlamaIndex + FastAPI
- Optional UI: Open WebUI

## Prereqs
- Python 3.11+
- Docker Desktop
- Ollama: `brew install ollama && ollama serve && ollama pull llama3.1`

## Quickstart
```bash
# 1) clone and enter
# git clone <your-repo> rag-demo && cd rag-demo

# 2) spin up qdrant
make qdrant-up

# 3) create venv & install deps
make setup

# 4) run API
make run

# 5) add PDFs to ./data, then ingest
make ingest

# 6) ask a question
make ask Q="How does a 2-pipe FCU handle switchover?"
```

## Endpoints

* `POST /ingest` → indexes PDFs/TXT/MD from `./data`
* `POST /chat` → `{ "q": "your question", "k": 4 }` - Full RAG with LLM
* `POST /chat-stream` → Same as `/chat` but streams response in real-time
* `POST /retrieve` → `{ "q": "your question", "k": 4 }` - Just retrieval, no LLM (instant)
* `GET /health` → Health check
* `GET /test-ollama` → Test Ollama connection

### cURL

```bash
# Ingest documents
curl -X POST localhost:8000/ingest

# Full RAG query (may be slow)
curl -X POST localhost:8000/chat -H 'Content-Type: application/json' \
  -d '{"q":"What is the heating sequence of operation for a fan coil?"}'

# Streaming (see partial results as they generate)
curl -N -X POST localhost:8000/chat-stream -H 'Content-Type: application/json' \
  -d '{"q":"What is Ciper 30?","k":2}'

# Fast retrieval only (no LLM, returns source chunks)
curl -X POST localhost:8000/retrieve -H 'Content-Type: application/json' \
  -d '{"q":"What is Ciper 30?","k":2}'
```

## Optional UI (Open WebUI)

```bash
docker run -d --name openwebui -p 3000:8080 \
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
  -e QDRANT_URI=http://host.docker.internal:6333 \
  ghcr.io/open-webui/open-webui:main
```

Open [http://localhost:3000](http://localhost:3000) and wire up your knowledge base.

## Performance Optimization

### LLM is Too Slow? (25+ minutes per query)

The default `llama3.1` model can be extremely. Here are solutions:

**Option 1: Use a Faster Model (RECOMMENDED)**

```bash
# Pull a fast model (choose one)
ollama pull qwen2.5:0.5b      # Ultra-fast (1-3 sec), good for demos
ollama pull phi3:mini         # Fast (5-10 sec), better quality
ollama pull gemma2:2b         # Fast (5-15 sec), good balance

# Update .env file
echo "OLLAMA_MODEL=qwen2.5:0.5b" >> .env

# Restart server
make run
```

**Option 2: Use Streaming**

See partial results as they're generated (better UX even if slow):

```bash
curl -N -X POST localhost:8000/chat-stream -H 'Content-Type: application/json' \
  -d '{"q":"What is Ciper 30?","k":2}'
```

**Option 3: Use Retrieval-Only**

Get instant results without LLM (returns relevant document chunks):

```bash
curl -X POST localhost:8000/retrieve -H 'Content-Type: application/json' \
  -d '{"q":"What is Ciper 30?","k":2}' | jq '.results[].text'
```

**Option 4: Reduce Context**

The app now automatically limits to 2 chunks max and uses shorter prompts.

### Speed Comparison

| Model | Response Time | Quality | Use Case |
|-------|--------------|---------|----------|
| qwen2.5:0.5b | 1-3 sec | Good | Fast demos, testing |
| phi3:mini | 5-10 sec | Better | Development |
| gemma2:2b | 5-15 sec | Good | Production-lite |
| llama3.1:8b | 25+ min | Best | Not recommended for Mac |

## Troubleshooting

* **Embedding dimension mismatch**: Not possible here; we use the same embed model for indexing + queries.
* **Docker on Apple Silicon**: Qdrant runs fine under Docker; Ollama is native.
* **LLM timeout**: Use `/retrieve` endpoint for instant results, or switch to a smaller model (see Performance section).
* **No vectors in Qdrant**: Check server logs during ingestion - should show "Collection now has X vectors".

## Production Upgrade

* Persist Qdrant volumes (already mounted).
* Add auth/HTTPS (Caddy/Traefik), evals/telemetry, and CI.
* Swap embeddings (e.g., `bge-base`) and consider Qdrant Cloud.
