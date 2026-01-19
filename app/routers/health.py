"""
Health check and diagnostic endpoints.
"""
import logging
from fastapi import APIRouter

from app.config import DATA_DIR, QDRANT_URL, LLM_PROFILE, OLLAMA_HOST
from app.llm import get_llm_provider, get_llm_info

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health")
@router.options("/health")  # Add OPTIONS support for CORS preflight
def health():
    """Basic health check endpoint."""
    info = get_llm_info()
    return {
        "status": "ok",
        "data_dir": DATA_DIR,
        "qdrant_url": QDRANT_URL,
        "llm_model": info.model,
        "llm_profile": info.profile,
        "gpu_accelerated": info.is_gpu_accelerated,
    }


@router.get("/health/llm")
def llm_health():
    """
    Detailed LLM health check with GPU detection and benchmark.

    Returns information about:
    - LLM provider and model
    - GPU detection results
    - Quick benchmark to verify performance
    """
    provider = get_llm_provider()
    info = get_llm_info()

    # Run health check
    is_healthy = provider.health_check()

    # Run quick benchmark
    benchmark = provider.benchmark()

    # Get available models
    try:
        available_models = provider.list_models()
    except Exception as e:
        logger.warning(f"Failed to list models: {e}")
        available_models = []

    return {
        "status": "ok" if is_healthy and benchmark.success else "degraded",
        "provider": info.provider,
        "model": info.model,
        "profile": info.profile,
        "host": info.host,
        "gpu": {
            "type": info.gpu_type,
            "name": info.gpu_name,
            "accelerated": info.is_gpu_accelerated,
        },
        "config": {
            "timeout": info.timeout,
            "max_tokens": info.max_tokens,
            "context_chunks": info.context_chunks,
        },
        "benchmark": {
            "success": benchmark.success,
            "latency_ms": benchmark.latency_ms,
            "likely_using_gpu": benchmark.likely_gpu,
            "error": benchmark.error,
        },
        "available_models": available_models[:10],  # Limit to first 10
    }


@router.get("/test-ollama")
def test_ollama():
    """Test Ollama connection with current model."""
    provider = get_llm_provider()
    info = get_llm_info()

    # Health check
    is_healthy = provider.health_check()
    if not is_healthy:
        return {
            "status": "error",
            "detail": f"Cannot connect to Ollama at {info.host}"
        }

    # Benchmark
    benchmark = provider.benchmark()

    return {
        "status": "success" if benchmark.success else "error",
        "model": info.model,
        "host": info.host,
        "latency_ms": benchmark.latency_ms,
        "gpu_type": info.gpu_type,
        "likely_using_gpu": benchmark.likely_gpu,
        "error": benchmark.error,
    }
