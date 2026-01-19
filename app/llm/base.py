"""
Abstract base class and models for LLM providers.

This module defines the interface that all LLM providers must implement,
enabling swappable backends (Ollama, vLLM, llama.cpp, etc.).
"""
from abc import ABC, abstractmethod
from typing import Optional, Any
from pydantic import BaseModel


class LLMConfig(BaseModel):
    """Configuration for an LLM provider."""
    provider: str = "ollama"
    model: str = "qwen2.5:1.5b"
    host: str = "http://localhost:11434"
    timeout: float = 300.0
    temperature: float = 0.0
    max_tokens: int = 500
    context_chunks: int = 4  # Recommended k value for retrieval

    class Config:
        extra = "allow"  # Allow additional provider-specific fields


class LLMInfo(BaseModel):
    """Runtime information about the LLM configuration."""
    provider: str
    model: str
    gpu_type: str  # "metal", "cuda", "rocm", "cpu"
    gpu_name: Optional[str] = None
    profile: str
    is_gpu_accelerated: bool
    host: str
    timeout: float
    max_tokens: int
    context_chunks: int


class BenchmarkResult(BaseModel):
    """Result of an LLM benchmark test."""
    success: bool
    latency_ms: Optional[float] = None
    likely_gpu: bool = False
    model: Optional[str] = None
    error: Optional[str] = None


class BaseLLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    All LLM backends must implement this interface to be usable
    with the daemonIQ RAG system.
    """

    def __init__(self, config: LLMConfig):
        self.config = config

    @abstractmethod
    def get_llm(self) -> Any:
        """
        Return a LlamaIndex-compatible LLM object.

        Returns:
            LLM object that can be assigned to Settings.llm
        """
        pass

    @abstractmethod
    def get_info(self) -> LLMInfo:
        """
        Return information about current LLM setup.

        Returns:
            LLMInfo with provider, model, GPU status, etc.
        """
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """
        Check if the LLM provider is responsive.

        Returns:
            True if provider is healthy, False otherwise
        """
        pass

    @abstractmethod
    def benchmark(self) -> BenchmarkResult:
        """
        Run a quick benchmark to measure performance.

        This can be used to verify GPU acceleration is active
        by checking inference latency.

        Returns:
            BenchmarkResult with latency and GPU likelihood
        """
        pass

    @abstractmethod
    def detect_gpu(self) -> dict:
        """
        Detect available GPU acceleration.

        Returns:
            Dict with gpu_available, gpu_type, gpu_name
        """
        pass
