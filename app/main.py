import os, glob
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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
Settings.llm = Ollama(
    model=OLLAMA_MODEL,
    request_timeout=300.0,
    temperature=0.0,  # Deterministic outputs - prevent hallucination
    additional_kwargs={"num_predict": 500}  # Allow detailed technical responses with lists
)
# 3) Chunker - optimized for BAS technical manuals
Settings.node_parser = SentenceSplitter(chunk_size=800, chunk_overlap=200)

client = QdrantClient(url=QDRANT_URL)

app = FastAPI()

# Add CORS middleware to allow requests from the UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (use specific origins in production)
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)

_index_cache = None


@app.get("/health")
@app.options("/health")  # Add OPTIONS support for CORS preflight
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


def build_index(force_rebuild=False):
    """
    Build or update the vector index.

    Args:
        force_rebuild: If True, deletes existing collection and rebuilds from scratch.
                      If False, only indexes new documents (incremental update).
    """
    logger.info(f"Starting ingestion from {DATA_DIR} (force_rebuild={force_rebuild})")

    # Load documents
    docs = SimpleDirectoryReader(DATA_DIR, required_exts=[".pdf", ".txt", ".md"]).load_data()
    logger.info(f"Loaded {len(docs)} documents from directory")

    # Check if collection exists
    collection_exists = False
    try:
        client.get_collection(COLLECTION)
        collection_exists = True
        logger.info(f"Collection {COLLECTION} already exists")
    except Exception:
        logger.info(f"Collection {COLLECTION} does not exist")

    if force_rebuild and collection_exists:
        # Delete and recreate collection
        client.delete_collection(COLLECTION)
        logger.info(f"Deleted existing collection {COLLECTION} for rebuild")
        collection_exists = False

    if not collection_exists:
        # Create new collection
        logger.info(f"Creating collection {COLLECTION} with dimension 384")
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config={"size": 384, "distance": "Cosine"}
        )

    # Create vector store
    vector_store = QdrantVectorStore(client=client, collection_name=COLLECTION)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    if collection_exists and not force_rebuild:
        # Incremental update: check which files are already indexed
        logger.info("Performing incremental update...")

        # Get existing filenames from Qdrant (paginate to handle large collections)
        indexed_files = set()
        offset = None

        while True:
            scroll_result = client.scroll(
                collection_name=COLLECTION,
                limit=100,  # Process in batches of 100
                offset=offset,
                with_payload=True,
                with_vectors=False
            )

            points, next_offset = scroll_result

            for point in points:
                if point.payload and "file_name" in point.payload:
                    indexed_files.add(point.payload["file_name"])

            # Break if no more results
            if next_offset is None:
                break

            offset = next_offset

        logger.info(f"Found {len(indexed_files)} files already indexed: {indexed_files}")

        # Filter to only new documents
        new_docs = [doc for doc in docs if doc.metadata.get("file_name") not in indexed_files]

        if len(new_docs) == 0:
            logger.info("✅ All documents already indexed. No new files to add.")
            # Return existing index
            index = VectorStoreIndex.from_vector_store(vector_store)
            collection_info = client.get_collection(COLLECTION)
            logger.info(f"Collection has {collection_info.points_count} vectors")
            return index

        logger.info(f"Found {len(new_docs)} new documents to index: {[d.metadata.get('file_name') for d in new_docs]}")
        docs = new_docs

    logger.info(f"Indexing {len(docs)} documents...")
    # Create/update index with documents
    if collection_exists and not force_rebuild:
        # Load existing index and add new documents
        index = VectorStoreIndex.from_vector_store(vector_store)
        for doc in docs:
            index.insert(doc)
        logger.info(f"Added {len(docs)} new documents to existing index")
    else:
        # Build fresh index
        index = VectorStoreIndex.from_documents(
            docs,
            storage_context=storage_context,
            show_progress=True
        )
        logger.info(f"Created new index with {len(docs)} documents")

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


class IngestReq(BaseModel):
    force_rebuild: bool = False  # Set to True to rebuild entire index


class IngestResp(BaseModel):
    files_indexed: int
    total_vectors: int
    mode: str  # "incremental" or "full_rebuild"


@app.post("/ingest", response_model=IngestResp)
def ingest(req: IngestReq = IngestReq()):
    try:
        logger.info(f"Starting ingestion from {DATA_DIR} (force_rebuild={req.force_rebuild})")

        # Check if directory exists
        if not os.path.exists(DATA_DIR):
            raise HTTPException(status_code=400, detail=f"Data directory not found: {DATA_DIR}")

        # Find files
        files = [p for p in glob.glob(f"{DATA_DIR}/*") if any(p.endswith(ext) for ext in [".pdf",".txt",".md"])]
        logger.info(f"Found {len(files)} files in data directory")

        if len(files) == 0:
            raise HTTPException(status_code=400, detail=f"No PDF, TXT, or MD files found in {DATA_DIR}")

        # Build index (incremental by default, unless force_rebuild=True)
        global _index_cache
        logger.info(f"Building index (force_rebuild={req.force_rebuild})...")
        _index_cache = build_index(force_rebuild=req.force_rebuild)

        # Get final count
        collection_info = client.get_collection(COLLECTION)
        total_vectors = collection_info.points_count

        mode = "full_rebuild" if req.force_rebuild else "incremental"
        logger.info(f"Successfully completed {mode} ingestion. Total vectors: {total_vectors}")

        return IngestResp(
            files_indexed=len(files),
            total_vectors=total_vectors,
            mode=mode
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during ingestion: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


class QueryReq(BaseModel):
    q: Optional[str] = None  # Accept "q" field
    query: Optional[str] = None  # Also accept "query" field (fallback)
    k: int = 4

    def get_query(self) -> str:
        """Get query from either 'q' or 'query' field"""
        if self.q:
            return self.q
        elif self.query:
            logger.warning(f"⚠️ Frontend sent 'query' instead of 'q' - using fallback")
            return self.query
        else:
            raise ValueError("Either 'q' or 'query' field is required")


@app.post("/retrieve")
def retrieve_only(req: QueryReq):
    """Retrieve relevant chunks without LLM generation - useful for testing"""
    try:
        query_text = req.get_query()  # Use helper to get query from either field
        logger.info(f"Retrieving chunks for: {query_text} (field: {'q' if req.q else 'query'})")
        index = get_or_build_index()
        retriever = index.as_retriever(similarity_top_k=req.k)
        nodes = retriever.retrieve(query_text)

        results = []
        for node in nodes:
            results.append({
                "score": node.score,
                "text": node.text,  # Full text for debugging
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
        query_text = req.get_query()  # Use helper to get query from either field
        logger.info(f"Querying: {query_text} (field: {'q' if req.q else 'query'})")
        index = get_or_build_index()

        # Use simpler settings for faster response
        from llama_index.core.prompts import PromptTemplate

        # BAS-SPECIFIC prompt optimized for technical manuals
        qa_prompt = PromptTemplate(
            "You are a Building Automation System (BAS) technical assistant specializing in Honeywell, Niagara, and CIPer systems.\n\n"
            "INSTRUCTIONS:\n"
            "- Answer ONLY using information from the context below\n"
            "- If the question asks 'what are' or 'list', format your answer as bullet points\n"
            "- For expansion modules, extract: model number, size/type, firmware version, DIP switch config, I/O capacity\n"
            "- Include specific details: model numbers, DIP switch settings, I/O specifications, wiring diagrams\n"
            "- If the context contains tables or specifications, extract ALL relevant details\n"
            "- Do NOT make up information or use external knowledge\n"
            "- If information is missing from context, acknowledge what is available and what is not\n\n"
            "Context from BAS documentation:\n{context_str}\n\n"
            "Question: {query_str}\n\n"
            "Answer (extract ALL relevant technical details from context):\n"
        )

        # Enforce minimum retrieval of 4 chunks
        top_k = max(req.k, 4)

        query_engine = index.as_query_engine(
            similarity_top_k=top_k,
            response_mode="compact",
            text_qa_template=qa_prompt,
            streaming=False
        )

        logger.info(f"Retrieving {top_k} chunks for RAG...")
        resp = query_engine.query(query_text)

        # Enhanced logging for debugging
        source_nodes = getattr(resp, "source_nodes", [])

        # Build simple sources array for UI compatibility (strings only)
        sources = [s.node.metadata.get("file_name", "") for s in source_nodes]

        # Log retrieval details for debugging
        logger.info(f"=== RETRIEVAL DEBUG ===")
        logger.info(f"Retrieved {len(source_nodes)} chunks")
        unique_files = set(sources)
        logger.info(f"Unique source files: {len(unique_files)} - {unique_files}")

        for i, node in enumerate(source_nodes):
            score = node.score if hasattr(node, 'score') else None
            page = node.node.metadata.get("page_label", "?")
            filename = node.node.metadata.get("file_name", "?")
            text_preview = node.text[:300].replace('\n', ' ')

            # Format score properly
            score_str = f"{score:.4f}" if isinstance(score, float) else "N/A"
            logger.info(f"Chunk {i+1}: score={score_str}, file={filename}, page={page}")
            logger.info(f"  Preview: {text_preview}...")

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
        query_text = req.get_query()  # Use helper to get query from either field
        logger.info(f"Streaming query: {query_text} (field: {'q' if req.q else 'query'})")
        index = get_or_build_index()

        from llama_index.core.prompts import PromptTemplate

        # BAS-SPECIFIC prompt for streaming (same as /chat)
        qa_prompt = PromptTemplate(
            "You are a Building Automation System (BAS) technical assistant specializing in Honeywell, Niagara, and CIPer systems.\n\n"
            "INSTRUCTIONS:\n"
            "- Answer ONLY using information from the context below\n"
            "- If the question asks 'what are' or 'list', format your answer as bullet points\n"
            "- Include specific details: model numbers, DIP switch settings, I/O specifications\n"
            "- Do NOT make up information or use external knowledge\n\n"
            "Context from BAS documentation:\n{context_str}\n\n"
            "Question: {query_str}\n\n"
            "Answer (extract ALL relevant technical details from context):\n"
        )

        # Enforce minimum retrieval of 4 chunks
        top_k = max(req.k, 4)

        query_engine = index.as_query_engine(
            similarity_top_k=top_k,
            response_mode="compact",
            text_qa_template=qa_prompt,
            streaming=True  # Enable streaming
        )

        def generate():
            streaming_response = query_engine.query(query_text)
            for text in streaming_response.response_gen:
                yield text

        return StreamingResponse(generate(), media_type="text/plain")
    except Exception as e:
        logger.error(f"Error during streaming: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Streaming failed: {str(e)}")
