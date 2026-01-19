"""
daemonIQ RAG API - Main application entry point.

A FastAPI application for Building Automation System (BAS) document retrieval
using RAG (Retrieval-Augmented Generation) with ontology grounding support.
"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from llama_index.core import Settings as LlamaSettings
from llama_index.core.callbacks import CallbackManager

from app.config import ENABLE_TRACING
from app.observability import setup_tracing, setup_metrics
from app.observability.callbacks import OTelLlamaIndexHandler
from app.observability.middleware import OTelMiddleware
from app.routers import health_router, ingest_router, query_router

# Import dependencies to initialize LlamaIndex settings
import app.dependencies  # noqa: F401

logger = logging.getLogger(__name__)

# Create FastAPI application
app = FastAPI(title="daemonIQ RAG API")

# Initialize OpenTelemetry observability
setup_tracing("daemoniq-rag")
setup_metrics("daemoniq-rag")

# Add tracing middleware if enabled
if ENABLE_TRACING:
    app.add_middleware(OTelMiddleware, service_name="daemoniq-rag")

    # Set up LlamaIndex callback handler for RAG event tracing
    otel_handler = OTelLlamaIndexHandler()
    callback_manager = CallbackManager([otel_handler])
    LlamaSettings.callback_manager = callback_manager
    logger.info("OpenTelemetry tracing enabled with LlamaIndex callback handler")

# Add CORS middleware to allow requests from the UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (use specific origins in production)
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)

# Include routers
app.include_router(health_router)
app.include_router(ingest_router)
app.include_router(query_router)
