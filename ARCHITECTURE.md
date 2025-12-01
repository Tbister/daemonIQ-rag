# DaemonIQ Architecture Overview

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER / CLIENT                            │
│                    (curl, browser, API client)                   │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP/REST
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Server                              │
│                    (app/main.py - port 8000)                     │
│                                                                   │
│  Endpoints:                                                       │
│  • POST /ingest      → Index documents                           │
│  • POST /chat        → Full RAG query                            │
│  • POST /chat-stream → Streaming RAG                             │
│  • POST /retrieve    → Vector search only                        │
│  • GET  /health      → Health check                              │
└────┬──────────────────────────┬────────────────────┬────────────┘
     │                          │                    │
     │ LlamaIndex               │                    │
     │                          │                    │
     ▼                          ▼                    ▼
┌──────────────┐      ┌──────────────────┐    ┌─────────────┐
│   Qdrant     │      │   FastEmbed      │    │   Ollama    │
│ Vector DB    │      │  (Embeddings)    │    │    (LLM)    │
│ port 6333    │      │ bge-small-en-v1.5│    │ port 11434  │
│              │      │   384 dims       │    │ qwen2.5:0.5b│
└──────────────┘      └──────────────────┘    └─────────────┘
     │ Docker                                        │ Local
     │                                               │
     ▼                                               ▼
┌──────────────┐                              ┌─────────────┐
│ Local Volume │                              │ ~/.ollama/  │
│ qdrant_storage                              │   models/   │
└──────────────┘                              └─────────────┘
```

---

## 📦 Component Breakdown

### 1. **FastAPI Server** (`app/main.py`)
**Role:** API layer & orchestration

**Key Functions:**
- `build_index()` - Loads PDFs, creates embeddings, stores in Qdrant
- `get_or_build_index()` - Retrieves or initializes index from Qdrant
- `ingest()` - Ingestion endpoint
- `retrieve_only()` - Vector search without LLM
- `chat()` - Full RAG with LLM generation
- `chat_stream()` - Streaming RAG response

**Tech:** Python 3.9, FastAPI, Uvicorn

---

### 2. **LlamaIndex** (RAG Orchestrator)
**Role:** Coordinates the RAG pipeline

**What it does:**
- Chunks documents (800 char chunks, 120 overlap)
- Generates embeddings via FastEmbed
- Manages vector storage in Qdrant
- Retrieves relevant chunks
- Sends context + query to LLM
- Returns synthesized answer

**Key Settings:**
```python
Settings.embed_model = FastEmbedEmbedding("BAAI/bge-small-en-v1.5")  # 384d
Settings.llm = Ollama("qwen2.5:0.5b")
Settings.node_parser = SentenceSplitter(chunk_size=800, overlap=120)
```

---

### 3. **Qdrant** (Vector Database)
**Role:** Store & search document embeddings

**Config:**
- Collection: `bas_docs`
- Vector dimension: 384
- Distance metric: Cosine
- Running in Docker on ports 6333-6334
- Persistent storage: `docker/qdrant_storage/`

**Operations:**
- **Write:** Store document chunk embeddings
- **Search:** Find top-k similar vectors for a query

---

### 4. **FastEmbed** (Embedding Model)
**Role:** Convert text → 384-dimensional vectors

**Model:** `BAAI/bge-small-en-v1.5`
- Small, fast embedding model
- 384 dimensions (compact)
- Used for BOTH documents AND queries (consistency)

**Process:**
```
"What is Ciper 30?"
    ↓ FastEmbed
[0.123, -0.456, 0.789, ...]  (384 numbers)
    ↓ Qdrant search
Top 2-4 most similar document chunks
```

---

### 5. **Ollama** (LLM Server)
**Role:** Generate natural language answers

**Current Model:** `qwen2.5:0.5b`
- 0.5 billion parameters
- Runs locally on Mac
- 1-3 second response time
- Alternative: `llama3.1` (better quality, 25+ min response)

**Process:**
```
Context: [relevant chunks from Qdrant]
Question: "What is Ciper 30?"
    ↓ Ollama LLM
"The Ciper 30 is a Honeywell controller..."
```

---

## 🔄 Data Flow

### Ingestion Flow (POST /ingest)
```
1. User uploads PDFs to /data directory
2. POST /ingest triggered
3. SimpleDirectoryReader loads PDFs
4. SentenceSplitter chunks documents (800 chars each)
5. FastEmbed generates 384d vectors for each chunk
6. VectorStoreIndex stores vectors in Qdrant
7. Returns: {"files_indexed": 2}
```

### Query Flow (POST /chat)
```
1. User sends: {"q": "What is Ciper 30?", "k": 4}
2. FastEmbed converts query → 384d vector
3. Qdrant searches for top-k similar chunks (cosine similarity)
4. LlamaIndex builds prompt:
   - Context: [top chunks]
   - Question: [user query]
5. Ollama LLM generates answer
6. Returns: {"answer": "...", "sources": ["file1.pdf", ...]}
```

### Retrieval-Only Flow (POST /retrieve)
```
1. User sends: {"q": "What is Ciper 30?", "k": 4}
2. FastEmbed converts query → 384d vector
3. Qdrant returns top-k chunks with scores
4. Returns: {"count": 4, "results": [{score, text, metadata}]}
   (No LLM involved - instant results)
```

---

## 📂 File Structure & Purpose

```
daemonIQ-rag/
├── app/
│   └── main.py                 # FastAPI app - ALL logic here
│
├── data/                       # Source documents (PDFs not in git)
│   └── README.md               # Instructions for adding documents
│
├── docker/
│   ├── qdrant.docker-compose.yml    # Qdrant container config
│   └── qdrant_storage/              # Persistent vector storage (not in git)
│
├── .venv/                      # Python virtual environment (gitignored)
│
├── .env                        # Runtime configuration (gitignored)
│   ├── OLLAMA_MODEL=qwen2.5:0.5b
│   ├── QDRANT_URL=http://localhost:6333
│   └── DATA_DIR=../data
│
├── .env.example                # Template configuration
├── Makefile                    # Dev commands (setup, run, ingest, etc.)
├── requirements.txt            # Python dependencies
├── README.md                   # User guide
├── QUICKSTART.md               # Quick start guide
└── ARCHITECTURE.md             # This file
```

---

## 🔌 API Endpoints Explained

### 1. `POST /ingest`
**Purpose:** Index all PDFs from `/data` directory
**Input:** None (reads from DATA_DIR)
**Output:** `{"files_indexed": 2}`
**What happens:** Chunks → Embeds → Stores in Qdrant

### 2. `POST /chat`
**Purpose:** Full RAG query with LLM
**Input:** `{"q": "your question", "k": 4}`
**Output:** `{"answer": "...", "sources": [...]}`
**Pipeline:** Query → Retrieve → LLM → Answer

### 3. `POST /chat-stream`
**Purpose:** Same as /chat but streams response word-by-word
**Input:** `{"q": "your question", "k": 2}`
**Output:** Streaming text (Server-Sent Events)
**Use case:** Better UX for slow LLMs

### 4. `POST /retrieve`
**Purpose:** Vector search only (no LLM)
**Input:** `{"q": "your question", "k": 4}`
**Output:** `{"count": 4, "results": [{score, text, metadata}]}`
**Speed:** Instant (<1 sec)

### 5. `GET /health`
**Purpose:** Service health check
**Output:** `{"status": "ok", "model": "qwen2.5:0.5b", ...}`

### 6. `GET /test-ollama`
**Purpose:** Test Ollama connectivity
**Output:** Direct Ollama API response

---

## 🧩 Tech Stack Summary

| Layer | Technology | Purpose |
|-------|------------|---------|
| **API** | FastAPI + Uvicorn | REST endpoints |
| **Orchestration** | LlamaIndex | RAG pipeline coordination |
| **Vector DB** | Qdrant (Docker) | Store & search embeddings |
| **Embeddings** | FastEmbed (bge-small-en-v1.5) | Text → 384d vectors |
| **LLM** | Ollama (qwen2.5:0.5b) | Answer generation |
| **Document Parsing** | PyPDF | Extract text from PDFs |
| **Chunking** | LlamaIndex SentenceSplitter | Split docs into 800-char chunks |

---

## 🔑 Key Design Decisions

### 1. **Same Embedding Model for Index & Query**
- Both use `bge-small-en-v1.5` (384d)
- Ensures consistency (no dimension mismatch)

### 2. **Small, Fast LLM**
- `qwen2.5:0.5b` chosen for speed (1-3 sec)
- Alternative: `llama3.1` for quality (25+ min)

### 3. **Docker for Qdrant Only**
- Qdrant in container for isolation
- Ollama runs natively on Mac for Metal acceleration

### 4. **Chunking Strategy**
- 800 chars per chunk
- 120 char overlap
- Balances context vs. precision

### 5. **Multiple Query Modes**
- `/chat` - Full RAG
- `/chat-stream` - Better UX for slow models
- `/retrieve` - Instant results without LLM

---

## 🎯 Current State

**Status:** 70% Complete

**Working:**
- ✅ Infrastructure (Qdrant, Ollama)
- ✅ API endpoints defined
- ✅ Fast model configured
- ✅ Documents ready

**Broken:**
- ❌ Vector ingestion (stores 0 vectors)
- ❌ Retrieval (no vectors to search)
- ❌ End-to-end RAG pipeline

**Blocker:** `VectorStoreIndex.from_documents()` not persisting vectors to Qdrant

---

## 📝 Quick Reference

### Start Services
```bash
make qdrant-up    # Start Qdrant (Docker)
ollama serve      # Start Ollama (if not running)
make run          # Start FastAPI
```

### Test Flow
```bash
make ingest                         # Index documents
make retrieve Q="What is Ciper 30?" # Test search
make ask Q="What is Ciper 30?"      # Test full RAG
```

### Check Status
```bash
docker ps | grep qdrant             # Qdrant running?
ps aux | grep ollama                # Ollama running?
curl localhost:8000/health          # FastAPI running?
curl localhost:6333/collections/bas_docs | jq .result.points_count  # Vectors stored?
```

---

**End of Architecture Overview**
