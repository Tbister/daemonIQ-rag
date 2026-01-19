"""
Shared dependencies: clients, caches, and LlamaIndex settings.
"""
import logging
from llama_index.core import VectorStoreIndex, Settings
from llama_index.embeddings.fastembed import FastEmbedEmbedding
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.core.node_parser import SentenceSplitter
from qdrant_client import QdrantClient

from app.config import QDRANT_URL, COLLECTION
from app.llm import get_llm, get_llm_info

logger = logging.getLogger(__name__)

# Initialize Qdrant client
client = QdrantClient(url=QDRANT_URL)

# Configure LlamaIndex settings
# 1) Embedding model for both ingest and query (384-d)
Settings.embed_model = FastEmbedEmbedding(model_name="BAAI/bge-small-en-v1.5")

# 2) LLM via modular provider (auto-detects GPU and selects appropriate model)
Settings.llm = get_llm()
llm_info = get_llm_info()
logger.info(
    f"LLM initialized: model={llm_info.model}, "
    f"profile={llm_info.profile}, "
    f"gpu={llm_info.gpu_type} ({llm_info.gpu_name or 'N/A'}), "
    f"accelerated={llm_info.is_gpu_accelerated}"
)

# 3) Chunker - optimized for BAS technical manuals
Settings.node_parser = SentenceSplitter(chunk_size=800, chunk_overlap=200)

# Index cache for lazy loading
_index_cache = None


def get_or_build_index() -> VectorStoreIndex:
    """Get cached index or load from Qdrant vector store."""
    global _index_cache
    if _index_cache is None:
        logger.info(f"Loading index from Qdrant collection: {COLLECTION}")
        vector_store = QdrantVectorStore(client=client, collection_name=COLLECTION)
        _index_cache = VectorStoreIndex.from_vector_store(vector_store)
        logger.info("Index loaded from vector store")
    return _index_cache


def set_index_cache(index: VectorStoreIndex) -> None:
    """Set the index cache (used after ingestion)."""
    global _index_cache
    _index_cache = index


def clear_index_cache() -> None:
    """Clear the index cache to force reload."""
    global _index_cache
    _index_cache = None
