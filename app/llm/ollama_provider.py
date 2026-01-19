"""
Ollama LLM provider implementation with GPU auto-detection.

This provider connects to an Ollama server (local or remote) and
automatically detects GPU acceleration (Metal, CUDA, ROCm).
"""
import logging
import platform
import subprocess
import time
from typing import Optional

import requests
from llama_index.llms.ollama import Ollama

from app.llm.base import BaseLLMProvider, LLMConfig, LLMInfo, BenchmarkResult

logger = logging.getLogger(__name__)


class OllamaProvider(BaseLLMProvider):
    """
    Ollama-based LLM provider with GPU auto-detection.

    Supports:
    - Local Ollama server
    - Remote Ollama server (for GPU offloading)
    - Metal (Apple Silicon)
    - CUDA (NVIDIA)
    - ROCm (AMD)
    """

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self._llm: Optional[Ollama] = None
        self._gpu_info: Optional[dict] = None

    def get_llm(self) -> Ollama:
        """
        Get or create the LlamaIndex Ollama LLM instance.

        Returns:
            Configured Ollama LLM object
        """
        if self._llm is None:
            logger.info(
                f"Initializing Ollama LLM: model={self.config.model}, "
                f"host={self.config.host}, timeout={self.config.timeout}s"
            )
            self._llm = Ollama(
                model=self.config.model,
                base_url=self.config.host,
                request_timeout=self.config.timeout,
                temperature=self.config.temperature,
                additional_kwargs={"num_predict": self.config.max_tokens}
            )
        return self._llm

    def detect_gpu(self) -> dict:
        """
        Detect available GPU acceleration.

        Checks for:
        - Apple Silicon (Metal) on macOS
        - ROCm (AMD) on Linux
        - CUDA (NVIDIA) on Linux/Windows

        Returns:
            Dict with gpu_available, gpu_type, gpu_name
        """
        if self._gpu_info is not None:
            return self._gpu_info

        gpu_info = {
            "gpu_available": False,
            "gpu_type": "cpu",
            "gpu_name": None,
            "vram_gb": None,
        }

        system = platform.system()
        logger.debug(f"Detecting GPU on {system}...")

        if system == "Darwin":  # macOS
            gpu_info = self._detect_macos_gpu(gpu_info)
        elif system == "Linux":
            gpu_info = self._detect_linux_gpu(gpu_info)
        elif system == "Windows":
            gpu_info = self._detect_windows_gpu(gpu_info)

        self._gpu_info = gpu_info
        logger.info(
            f"GPU detection result: type={gpu_info['gpu_type']}, "
            f"available={gpu_info['gpu_available']}, name={gpu_info['gpu_name']}"
        )
        return gpu_info

    def _detect_macos_gpu(self, gpu_info: dict) -> dict:
        """Detect Metal GPU on macOS (Apple Silicon)."""
        try:
            # Check CPU type - Apple Silicon has unified memory GPU
            result = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True,
                text=True,
                timeout=5
            )
            cpu_brand = result.stdout.strip()

            if "Apple" in cpu_brand:
                gpu_info["gpu_available"] = True
                gpu_info["gpu_type"] = "metal"
                gpu_info["gpu_name"] = cpu_brand

                # Try to get memory info (unified memory on Apple Silicon)
                try:
                    mem_result = subprocess.run(
                        ["sysctl", "-n", "hw.memsize"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    mem_bytes = int(mem_result.stdout.strip())
                    gpu_info["vram_gb"] = round(mem_bytes / (1024**3), 1)
                except Exception:
                    pass

                logger.debug(f"Detected Apple Silicon: {cpu_brand}")
            else:
                logger.debug(f"Intel Mac detected: {cpu_brand}, no Metal GPU acceleration")

        except subprocess.TimeoutExpired:
            logger.warning("Timeout detecting macOS GPU")
        except Exception as e:
            logger.warning(f"Error detecting macOS GPU: {e}")

        return gpu_info

    def _detect_linux_gpu(self, gpu_info: dict) -> dict:
        """Detect ROCm (AMD) or CUDA (NVIDIA) GPU on Linux."""
        # Try ROCm first (AMD)
        try:
            result = subprocess.run(
                ["rocminfo"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0 and "GPU" in result.stdout:
                gpu_info["gpu_available"] = True
                gpu_info["gpu_type"] = "rocm"

                # Parse GPU name from rocminfo
                for line in result.stdout.split("\n"):
                    if "Marketing Name:" in line:
                        gpu_info["gpu_name"] = line.split(":")[-1].strip()
                        break
                    elif "Name:" in line and "gfx" in line.lower():
                        gpu_info["gpu_name"] = line.split(":")[-1].strip()

                logger.debug(f"Detected ROCm GPU: {gpu_info['gpu_name']}")
                return gpu_info

        except FileNotFoundError:
            logger.debug("rocminfo not found, checking for NVIDIA CUDA...")
        except subprocess.TimeoutExpired:
            logger.warning("Timeout running rocminfo")
        except Exception as e:
            logger.debug(f"ROCm detection error: {e}")

        # Try CUDA (NVIDIA)
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                gpu_info["gpu_available"] = True
                gpu_info["gpu_type"] = "cuda"

                # Parse output: "NVIDIA GeForce RTX 4090, 24576 MiB"
                parts = result.stdout.strip().split(",")
                gpu_info["gpu_name"] = parts[0].strip()
                if len(parts) > 1:
                    try:
                        mem_mib = int(parts[1].strip().replace("MiB", "").strip())
                        gpu_info["vram_gb"] = round(mem_mib / 1024, 1)
                    except ValueError:
                        pass

                logger.debug(f"Detected CUDA GPU: {gpu_info['gpu_name']}")

        except FileNotFoundError:
            logger.debug("nvidia-smi not found, no NVIDIA GPU detected")
        except subprocess.TimeoutExpired:
            logger.warning("Timeout running nvidia-smi")
        except Exception as e:
            logger.debug(f"CUDA detection error: {e}")

        return gpu_info

    def _detect_windows_gpu(self, gpu_info: dict) -> dict:
        """Detect CUDA (NVIDIA) GPU on Windows."""
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=10,
                shell=True  # Needed for Windows PATH resolution
            )
            if result.returncode == 0 and result.stdout.strip():
                gpu_info["gpu_available"] = True
                gpu_info["gpu_type"] = "cuda"

                parts = result.stdout.strip().split(",")
                gpu_info["gpu_name"] = parts[0].strip()
                if len(parts) > 1:
                    try:
                        mem_mib = int(parts[1].strip().replace("MiB", "").strip())
                        gpu_info["vram_gb"] = round(mem_mib / 1024, 1)
                    except ValueError:
                        pass

        except Exception as e:
            logger.debug(f"Windows GPU detection error: {e}")

        return gpu_info

    def get_info(self) -> LLMInfo:
        """
        Get information about current LLM configuration.

        Returns:
            LLMInfo with provider details and GPU status
        """
        gpu = self.detect_gpu()
        return LLMInfo(
            provider="ollama",
            model=self.config.model,
            gpu_type=gpu["gpu_type"],
            gpu_name=gpu["gpu_name"],
            profile=getattr(self.config, "profile_name", "unknown"),
            is_gpu_accelerated=gpu["gpu_available"],
            host=self.config.host,
            timeout=self.config.timeout,
            max_tokens=self.config.max_tokens,
            context_chunks=self.config.context_chunks,
        )

    def health_check(self) -> bool:
        """
        Check if Ollama server is responsive.

        Returns:
            True if server responds to health check
        """
        try:
            response = requests.get(
                f"{self.config.host}/api/tags",
                timeout=5
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Ollama health check failed: {e}")
            return False

    def benchmark(self) -> BenchmarkResult:
        """
        Run a quick benchmark to verify GPU acceleration.

        A simple prompt on GPU typically completes in <2s.
        On CPU, even a small model takes >3s.

        Returns:
            BenchmarkResult with latency and GPU likelihood
        """
        prompt = "Say 'OK' if you can read this."
        start = time.time()

        try:
            response = requests.post(
                f"{self.config.host}/api/generate",
                json={
                    "model": self.config.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"num_predict": 10}
                },
                timeout=30
            )
            elapsed = time.time() - start
            latency_ms = elapsed * 1000

            if response.status_code == 200:
                return BenchmarkResult(
                    success=True,
                    latency_ms=latency_ms,
                    likely_gpu=latency_ms < 2000,  # GPU typically <2s
                    model=self.config.model
                )
            else:
                return BenchmarkResult(
                    success=False,
                    error=f"HTTP {response.status_code}: {response.text[:100]}"
                )

        except requests.exceptions.Timeout:
            return BenchmarkResult(
                success=False,
                error="Benchmark timed out after 30s"
            )
        except requests.exceptions.ConnectionError as e:
            return BenchmarkResult(
                success=False,
                error=f"Cannot connect to Ollama at {self.config.host}: {e}"
            )
        except Exception as e:
            return BenchmarkResult(
                success=False,
                error=str(e)
            )

    def list_models(self) -> list:
        """
        List models available on the Ollama server.

        Returns:
            List of model names
        """
        try:
            response = requests.get(
                f"{self.config.host}/api/tags",
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception as e:
            logger.warning(f"Failed to list Ollama models: {e}")

        return []

    def model_exists(self, model_name: str) -> bool:
        """
        Check if a specific model is available.

        Args:
            model_name: Model name to check (e.g., "mistral:7b")

        Returns:
            True if model is available
        """
        models = self.list_models()
        # Handle both exact match and partial match (mistral:7b vs mistral:7b-instruct)
        return any(
            model_name == m or model_name.split(":")[0] == m.split(":")[0]
            for m in models
        )
