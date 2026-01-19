"""
LLM module for daemonIQ RAG.

Provides a modular, swappable LLM backend with automatic GPU detection.

Usage:
    from app.llm import get_llm, get_llm_info, get_llm_provider

    # Get LlamaIndex LLM object for Settings.llm
    llm = get_llm()

    # Get info about current configuration
    info = get_llm_info()
    print(f"Using {info.model} on {info.gpu_type}")

    # Get recommended k value based on profile
    k = get_recommended_k()

Environment Variables:
    LLM_PROVIDER: Provider type (default: "ollama")
    LLM_PROFILE: Profile name (auto, cpu, gpu, dev, prod, bas_optimized)
    OLLAMA_HOST: Ollama server URL (default: http://localhost:11434)
    OLLAMA_MODEL: Override model name (optional)
"""
import logging
import os
from typing import Any, Optional

from app.llm.base import BaseLLMProvider, LLMConfig, LLMInfo
from app.llm.profiles import (
    LLM_PROFILES,
    SAFE_DEFAULTS,
    MODEL_FALLBACK_CHAIN,
    get_profile,
    get_profile_for_gpu,
)
from app.llm.ollama_provider import OllamaProvider

logger = logging.getLogger(__name__)

# Singleton instance
_provider_instance: Optional[BaseLLMProvider] = None
_resolved_profile: Optional[str] = None


def _resolve_profile() -> tuple[str, dict]:
    """
    Resolve the LLM profile based on environment and GPU detection.

    Returns:
        Tuple of (profile_name, profile_config)
    """
    profile_name = os.getenv("LLM_PROFILE", "auto")
    logger.info(f"Resolving LLM profile: {profile_name}")

    if profile_name == "auto":
        # Auto-detect GPU and select appropriate profile
        temp_config = LLMConfig(
            host=os.getenv("OLLAMA_HOST", "http://localhost:11434")
        )
        temp_provider = OllamaProvider(temp_config)
        gpu_info = temp_provider.detect_gpu()

        profile_name = get_profile_for_gpu(
            gpu_available=gpu_info["gpu_available"],
            gpu_type=gpu_info["gpu_type"]
        )
        logger.info(
            f"Auto-detected profile: {profile_name} "
            f"(GPU: {gpu_info['gpu_type']}, available: {gpu_info['gpu_available']})"
        )

    profile = get_profile(profile_name)
    return profile_name, profile


def _resolve_model(profile: dict, provider: OllamaProvider) -> str:
    """
    Resolve the model to use, with fallback chain.

    Priority:
    1. OLLAMA_MODEL env var (if set and not "auto")
    2. Profile's model
    3. Fallback chain based on availability

    Args:
        profile: Profile configuration dict
        provider: OllamaProvider instance for checking model availability

    Returns:
        Model name to use
    """
    # Check env var override first
    env_model = os.getenv("OLLAMA_MODEL")
    if env_model and env_model != "auto":
        logger.info(f"Using model from OLLAMA_MODEL env var: {env_model}")
        return env_model

    # Use profile's model if it's not "auto"
    profile_model = profile.get("model", "auto")
    if profile_model != "auto":
        # Check if it exists, fall back if not
        if provider.model_exists(profile_model):
            logger.info(f"Using profile model: {profile_model}")
            return profile_model
        else:
            logger.warning(
                f"Profile model {profile_model} not found, trying fallback chain"
            )

    # Try fallback chain
    for model in MODEL_FALLBACK_CHAIN:
        if provider.model_exists(model):
            logger.info(f"Using fallback model: {model}")
            return model

    # Last resort: use first available model
    available = provider.list_models()
    if available:
        model = available[0]
        logger.warning(f"Using first available model as last resort: {model}")
        return model

    # Ultimate fallback
    logger.error("No models available, using safe default (may fail)")
    return SAFE_DEFAULTS["model"]


def get_llm_provider() -> BaseLLMProvider:
    """
    Get the configured LLM provider instance (singleton).

    Creates and caches the provider on first call. Subsequent calls
    return the cached instance.

    Returns:
        Configured LLM provider
    """
    global _provider_instance, _resolved_profile

    if _provider_instance is not None:
        return _provider_instance

    provider_type = os.getenv("LLM_PROVIDER", "ollama")
    logger.info(f"Initializing LLM provider: {provider_type}")

    if provider_type != "ollama":
        raise ValueError(
            f"Unknown LLM provider: {provider_type}. "
            f"Currently only 'ollama' is supported."
        )

    # Resolve profile
    profile_name, profile = _resolve_profile()
    _resolved_profile = profile_name

    # Create temporary provider to check model availability
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    temp_config = LLMConfig(host=host)
    temp_provider = OllamaProvider(temp_config)

    # Resolve model with fallback
    model = _resolve_model(profile, temp_provider)

    # Build final config
    config = LLMConfig(
        provider=provider_type,
        model=model,
        host=host,
        timeout=profile.get("timeout", SAFE_DEFAULTS["timeout"]),
        temperature=profile.get("temperature", SAFE_DEFAULTS["temperature"]),
        max_tokens=profile.get("max_tokens", SAFE_DEFAULTS["max_tokens"]),
        context_chunks=profile.get("context_chunks", SAFE_DEFAULTS["context_chunks"]),
    )
    # Store profile name for info
    config.profile_name = profile_name

    # Create provider
    _provider_instance = OllamaProvider(config)

    logger.info(
        f"LLM provider initialized: model={config.model}, "
        f"profile={profile_name}, host={config.host}"
    )

    return _provider_instance


def get_llm() -> Any:
    """
    Get the LlamaIndex-compatible LLM object.

    This is the main function to use when setting up LlamaIndex:
        Settings.llm = get_llm()

    Returns:
        LLM object for LlamaIndex
    """
    return get_llm_provider().get_llm()


def get_llm_info() -> LLMInfo:
    """
    Get information about current LLM configuration.

    Useful for logging, debugging, and health endpoints.

    Returns:
        LLMInfo with provider, model, GPU status, etc.
    """
    return get_llm_provider().get_info()


def get_recommended_k() -> int:
    """
    Get recommended number of chunks based on current profile.

    CPU profiles use fewer chunks to reduce inference time.
    GPU profiles can handle more context.

    Returns:
        Recommended k value for retrieval
    """
    return get_llm_provider().config.context_chunks


def reset_provider() -> None:
    """
    Reset the provider singleton.

    Useful for testing or when configuration changes.
    """
    global _provider_instance, _resolved_profile
    _provider_instance = None
    _resolved_profile = None
    logger.info("LLM provider reset")


# Export public API
__all__ = [
    "get_llm",
    "get_llm_info",
    "get_llm_provider",
    "get_recommended_k",
    "reset_provider",
    "LLMConfig",
    "LLMInfo",
]
