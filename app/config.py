"""
Configuration settings loaded from environment variables.
"""
import os
import logging
from dotenv import load_dotenv

load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Data and storage settings
DATA_DIR = os.getenv("DATA_DIR", "../data")
DATA_DIR = os.path.abspath(DATA_DIR)  # Resolve to absolute path

COLLECTION = os.getenv("QDRANT_COLLECTION", "bas_docs")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")

# LLM settings (modular GPU-accelerated backend)
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")
LLM_PROFILE = os.getenv("LLM_PROFILE", "auto")  # auto, cpu, gpu, dev, prod, bas_optimized
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "auto")  # "auto" = select based on profile

# Phase 1B: Grounded retrieval configuration
RETRIEVAL_MODE = os.getenv("RETRIEVAL_MODE", "vanilla")  # "vanilla" or "grounded"
GROUNDED_MIN_CONF = float(os.getenv("GROUNDED_MIN_CONF", "0.6"))
GROUNDED_LIMIT_MULT = int(os.getenv("GROUNDED_LIMIT_MULT", "4"))
LOG_GROUNDED_RETRIEVAL = os.getenv("LOG_GROUNDED_RETRIEVAL", "0") == "1"

# Observability settings
ENABLE_TRACING = os.getenv("ENABLE_TRACING", "false").lower() == "true"

# Log configuration on startup
logger.info(f"Data directory: {DATA_DIR}")
logger.info(f"Qdrant URL: {QDRANT_URL}")
logger.info(f"Collection: {COLLECTION}")
logger.info(f"LLM: provider={LLM_PROVIDER}, profile={LLM_PROFILE}, host={OLLAMA_HOST}, model={OLLAMA_MODEL}")
logger.info(f"Retrieval mode: {RETRIEVAL_MODE} (grounded_min_conf={GROUNDED_MIN_CONF}, limit_mult={GROUNDED_LIMIT_MULT})")
