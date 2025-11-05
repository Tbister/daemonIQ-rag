import os, glob
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import logging

from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings, StorageContext
from llama_index.embeddings.fastembed import FastEmbedEmbedding
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.core.node_parser import SentenceSplitter
from llama_index.llms.ollama import Ollama
from qdrant_client import QdrantClient

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

DATA_DIR = os.getenv("DATA_DIR", "../data")
COLLECTION = os.getenv("QDRANT_COLLECTION", "bas_docs")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")

# Resolve absolute path for data directory
DATA_DIR = os.path.abspath(DATA_DIR)
logger.info(f"Data directory: {DATA_DIR}")
logger.info(f"Qdrant URL: {QDRANT_URL}")
logger.info(f"Collection: {COLLECTION}")

# 1) One embedding model for BOTH ingest and query (384-d)
Settings.embed_model = FastEmbedEmbedding(model_name="BAAI/bge-small-en-v1.5")
# 2) Local LLM via Ollama (increased timeout for first query)
Settings.llm = Ollama(model=OLLAMA_MODEL, request_timeout=300.0)
# 3) Chunker
Settings.node_parser = SentenceSplitter(chunk_size=800, chunk_overlap=120)

client = QdrantClient(url=QDRANT_URL)

app = FastAPI()
_index_cache = None


@app.get("/health")
def health():
    """Health check endpoint"""
    return {
        "status": "ok",
        "data_dir": DATA_DIR,
        "qdrant_url": QDRANT_URL,
        "model": OLLAMA_MODEL
    }


@app.get("/test-ollama")
def test_ollama():
    """Test Ollama connection directly"""
    try:
        import requests
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": "Say 'OK' if you can read this.", "stream": False},
            timeout=30
        )
        return {"status": "success", "response": response.json()}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


def build_index():
    logger.info(f"Starting ingestion from {DATA_DIR}")

    # Load documents
    docs = SimpleDirectoryReader(DATA_DIR, required_exts=[".pdf", ".txt", ".md"]).load_data()
    logger.info(f"Loaded {len(docs)} documents from directory")

    # Recreate collection to ensure clean state
    try:
        client.delete_collection(COLLECTION)
        logger.info(f"Deleted existing collection {COLLECTION}")
    except Exception:
        logger.info(f"Collection {COLLECTION} did not exist")

    logger.info(f"Creating fresh collection {COLLECTION} with dimension 384")
    client.create_collection(
        collection_name=COLLECTION,
        vectors_config={"size": 384, "distance": "Cosine"}
    )

    # Create vector store AFTER collection exists
    vector_store = QdrantVectorStore(client=client, collection_name=COLLECTION)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    logger.info(f"Building index with {len(docs)} documents...")
    # Create index with proper storage context
    index = VectorStoreIndex.from_documents(
        docs,
        storage_context=storage_context,
        show_progress=True
    )
    logger.info(f"Index created successfully")

    # Verify vectors were stored
    collection_info = client.get_collection(COLLECTION)
    vector_count = collection_info.points_count
    logger.info(f"✅ Collection now has {vector_count} vectors")

    if vector_count == 0:
        logger.error("⚠️ WARNING: No vectors were stored! Check embeddings configuration.")

    return index


def get_or_build_index():
    global _index_cache
    if _index_cache is None:
        logger.info(f"Loading index from Qdrant collection: {COLLECTION}")
        # Create vector store and load existing index
        vector_store = QdrantVectorStore(client=client, collection_name=COLLECTION)
        _index_cache = VectorStoreIndex.from_vector_store(vector_store)
        logger.info("Index loaded from vector store")
    return _index_cache


class IngestResp(BaseModel):
    files_indexed: int


@app.post("/ingest", response_model=IngestResp)
def ingest():
    try:
        logger.info(f"Starting ingestion from {DATA_DIR}")

        # Check if directory exists
        if not os.path.exists(DATA_DIR):
            raise HTTPException(status_code=400, detail=f"Data directory not found: {DATA_DIR}")

        # Find files
        files = [p for p in glob.glob(f"{DATA_DIR}/*") if any(p.endswith(ext) for ext in [".pdf",".txt",".md"])]
        logger.info(f"Found {len(files)} files: {files}")

        if len(files) == 0:
            raise HTTPException(status_code=400, detail=f"No PDF, TXT, or MD files found in {DATA_DIR}")

        # Build index
        global _index_cache
        logger.info("Building index...")
        _index_cache = build_index()
        logger.info(f"Successfully indexed {len(files)} files")

        return IngestResp(files_indexed=len(files))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during ingestion: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


class QueryReq(BaseModel):
    q: str
    k: int = 4


@app.post("/retrieve")
def retrieve_only(req: QueryReq):
    """Retrieve relevant chunks without LLM generation - useful for testing"""
    try:
        logger.info(f"Retrieving chunks for: {req.q}")
        index = get_or_build_index()
        retriever = index.as_retriever(similarity_top_k=req.k)
        nodes = retriever.retrieve(req.q)

        results = []
        for node in nodes:
            results.append({
                "score": node.score,
                "text": node.text[:200] + "...",  # First 200 chars
                "metadata": node.metadata
            })

        logger.info(f"Retrieved {len(results)} chunks")
        return {"count": len(results), "results": results}
    except Exception as e:
        logger.error(f"Error during retrieval: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Retrieval failed: {str(e)}")


@app.post("/chat")
def chat(req: QueryReq):
    try:
        logger.info(f"Querying: {req.q}")
        index = get_or_build_index()

        # Use simpler settings for faster response
        from llama_index.core.prompts import PromptTemplate

        # Shorter, more direct prompt
        qa_prompt = PromptTemplate(
            "Context: {context_str}\n\n"
            "Question: {query_str}\n\n"
            "Give a brief, direct answer (2-3 sentences max):\n"
        )

        query_engine = index.as_query_engine(
            similarity_top_k=min(req.k, 2),  # Max 2 chunks to reduce context
            response_mode="compact",
            text_qa_template=qa_prompt,
            streaming=False
        )

        logger.info("Sending query to LLM...")
        resp = query_engine.query(req.q)

        sources = [s.node.metadata.get("file_name", "") for s in getattr(resp, "source_nodes", [])]
        logger.info(f"Query completed. Sources: {sources}")
        return {"answer": str(resp), "sources": sources}
    except TimeoutError:
        logger.error("LLM query timed out after 300 seconds")
        raise HTTPException(status_code=504, detail="LLM query timed out. Try: 1) Reduce k value, 2) Ask simpler question, 3) Check Ollama logs")
    except Exception as e:
        logger.error(f"Error during query: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@app.post("/chat-stream")
def chat_stream(req: QueryReq):
    """Streaming endpoint - shows partial results as they're generated"""
    try:
        logger.info(f"Streaming query: {req.q}")
        index = get_or_build_index()

        from llama_index.core.prompts import PromptTemplate
        qa_prompt = PromptTemplate(
            "Context: {context_str}\n\n"
            "Question: {query_str}\n\n"
            "Give a brief, direct answer (2-3 sentences max):\n"
        )

        query_engine = index.as_query_engine(
            similarity_top_k=min(req.k, 2),
            response_mode="compact",
            text_qa_template=qa_prompt,
            streaming=True  # Enable streaming
        )

        def generate():
            streaming_response = query_engine.query(req.q)
            for text in streaming_response.response_gen:
                yield text

        return StreamingResponse(generate(), media_type="text/plain")
    except Exception as e:
        logger.error(f"Error during streaming: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Streaming failed: {str(e)}")
