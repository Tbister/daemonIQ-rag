"""
LLM Profile configurations for different deployment scenarios.

Profiles define recommended settings for various hardware configurations
and use cases. The 'auto' profile will detect GPU availability and select
the appropriate profile automatically.
"""

# Model fallback chain - try these in order if preferred model unavailable
MODEL_FALLBACK_CHAIN = [
    "mistral:7b",      # Preferred: best for technical content
    "llama3.2:3b",     # Fallback: smaller but capable
    "phi3:mini",       # Fallback: good instruction following
    "qwen2.5:1.5b",    # Fallback: fast CPU option
    "qwen2.5:0.5b",    # Last resort: current model
]

# Profile definitions
LLM_PROFILES = {
    "auto": {
        "description": "Auto-detect GPU and select appropriate profile",
        "model": "auto",  # Will be resolved at runtime
        "max_tokens": 500,
        "context_chunks": 4,
        "timeout": 120,
        "temperature": 0.0,
    },
    "cpu": {
        "description": "CPU-optimized: smaller model, reduced context for faster response",
        "model": "qwen2.5:1.5b",
        "max_tokens": 300,
        "context_chunks": 2,  # Reduce context to speed up inference
        "timeout": 180,       # Allow more time for CPU inference
        "temperature": 0.0,
    },
    "gpu": {
        "description": "GPU-optimized: larger model, full context for best quality",
        "model": "mistral:7b",
        "max_tokens": 500,
        "context_chunks": 4,
        "timeout": 120,       # Allow time for larger model inference
        "temperature": 0.0,
    },
    "dev": {
        "description": "Development: fast iteration, lower quality acceptable",
        "model": "qwen2.5:0.5b",
        "max_tokens": 200,
        "context_chunks": 2,
        "timeout": 60,
        "temperature": 0.0,
    },
    "prod": {
        "description": "Production: best quality, GPU required",
        "model": "llama3.1:8b",
        "max_tokens": 500,
        "context_chunks": 4,
        "timeout": 120,
        "temperature": 0.0,
    },
    "bas_optimized": {
        "description": "BAS-specific: technical accuracy focus with mistral",
        "model": "mistral:7b",
        "max_tokens": 500,
        "context_chunks": 4,
        "timeout": 90,
        "temperature": 0.0,  # No creativity, just facts
    },
    "fast": {
        "description": "Fast response: minimal latency, lower quality",
        "model": "qwen2.5:0.5b",
        "max_tokens": 150,
        "context_chunks": 1,  # Single chunk for speed
        "timeout": 30,
        "temperature": 0.0,
    },
}

# Safe defaults if everything else fails
SAFE_DEFAULTS = {
    "model": "qwen2.5:1.5b",
    "max_tokens": 300,
    "context_chunks": 2,
    "timeout": 180,
    "temperature": 0.0,
}


def get_profile(name: str) -> dict:
    """
    Get a profile by name with safe defaults.

    Args:
        name: Profile name (auto, cpu, gpu, dev, prod, bas_optimized, fast)

    Returns:
        Profile dict with all required fields
    """
    profile = LLM_PROFILES.get(name, SAFE_DEFAULTS).copy()

    # Ensure all required fields exist
    for key, value in SAFE_DEFAULTS.items():
        if key not in profile:
            profile[key] = value

    return profile


def get_profile_for_gpu(gpu_available: bool, gpu_type: str = "cpu") -> str:
    """
    Select appropriate profile based on GPU availability.

    Args:
        gpu_available: Whether GPU acceleration is available
        gpu_type: Type of GPU (metal, cuda, rocm, cpu)

    Returns:
        Profile name to use
    """
    if not gpu_available:
        return "cpu"

    # All GPU types get the same profile for now
    # Could differentiate based on VRAM in future
    return "gpu"
