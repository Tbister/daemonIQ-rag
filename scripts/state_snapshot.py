#!/usr/bin/env python3
"""
Generate a STATE.md-compatible snapshot of current service wiring.

Reads from:
  - .env file (if present)
  - /health endpoint (if RAG service is running)

Usage:
  python scripts/state_snapshot.py
  python scripts/state_snapshot.py --check-services  # Also ping services

Output is copy-paste ready for STATE.md sections.
"""

import os
import sys
from pathlib import Path

# Find project root (parent of scripts/)
PROJECT_ROOT = Path(__file__).parent.parent
ENV_FILE = PROJECT_ROOT / ".env"


def parse_env_file():
    """Parse .env file and return dict of key=value pairs."""
    env_vars = {}
    if not ENV_FILE.exists():
        return env_vars

    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                env_vars[key.strip()] = value.strip()
    return env_vars


def get_env(key, default=None, env_vars=None):
    """Get env var from parsed .env or os.environ."""
    if env_vars and key in env_vars:
        return env_vars[key]
    return os.environ.get(key, default)


def check_service(url, name):
    """Try to reach a service health endpoint."""
    try:
        import requests
        resp = requests.get(f"{url}/health", timeout=2)
        if resp.status_code == 200:
            return "Running"
        return f"HTTP {resp.status_code}"
    except Exception as e:
        return f"Unreachable ({type(e).__name__})"


def main():
    check_services = "--check-services" in sys.argv

    env_vars = parse_env_file()

    # Extract known config values
    rag_port = get_env("RAG_PORT", "8000", env_vars)
    rag_url = get_env("RAG_URL", f"http://localhost:{rag_port}", env_vars)
    bas_url = get_env("BAS_ONTOLOGY_URL", "http://localhost:8001", env_vars)
    qdrant_url = get_env("QDRANT_URL", "http://localhost:6333", env_vars)
    ollama_model = get_env("OLLAMA_MODEL", "qwen2.5:0.5b", env_vars)
    collection = get_env("QDRANT_COLLECTION", "bas_docs", env_vars)
    retrieval_mode = get_env("RETRIEVAL_MODE", "vanilla", env_vars)
    min_conf = get_env("GROUNDED_MIN_CONF", "0.6", env_vars)
    limit_mult = get_env("GROUNDED_LIMIT_MULT", "4", env_vars)

    # Derive ports from URLs
    def port_from_url(url):
        if ":" in url.split("//")[-1]:
            return url.split(":")[-1].split("/")[0]
        return "80"

    print("=" * 60)
    print("STATE.md Snapshot")
    print("=" * 60)
    print()

    # Services & Ports
    print("## Services & Ports")
    print()
    print("| Service | Port | Status | Notes |")
    print("|---------|------|--------|-------|")

    services = [
        ("daemonIQ-rag API", rag_url, "FastAPI, uvicorn"),
        ("BAS-Ontology", bas_url, "External grounding service"),
        ("Qdrant", qdrant_url, "Docker container"),
        ("Ollama", "http://localhost:11434", f"Model: {ollama_model}"),
    ]

    for name, url, notes in services:
        port = port_from_url(url)
        if check_services:
            status = check_service(url, name)
        else:
            status = "(not checked)"
        print(f"| {name} | {port} | {status} | {notes} |")

    print()

    # Environment Variables
    print("## Environment Variables")
    print()
    print("```bash")
    print("# Core")
    print(f"DATA_DIR={get_env('DATA_DIR', '../data', env_vars)}")
    print(f"QDRANT_COLLECTION={collection}")
    print(f"QDRANT_URL={qdrant_url}")
    print(f"OLLAMA_MODEL={ollama_model}")
    print()
    print("# Grounding (Phase 1A)")
    print(f"BAS_ONTOLOGY_URL={bas_url}")
    print()
    print("# Retrieval (Phase 1B)")
    print(f"RETRIEVAL_MODE={retrieval_mode}")
    print(f"GROUNDED_MIN_CONF={min_conf}")
    print(f"GROUNDED_LIMIT_MULT={limit_mult}")
    print(f"LOG_GROUNDED_RETRIEVAL={get_env('LOG_GROUNDED_RETRIEVAL', '0', env_vars)}")
    print("```")
    print()

    # Current Models
    print("## Current Models & Versions")
    print()
    print("| Component | Model/Version | Notes |")
    print("|-----------|---------------|-------|")
    print(f"| Embeddings | `BAAI/bge-small-en-v1.5` | 384 dimensions, via FastEmbed |")
    print(f"| LLM | `{ollama_model}` | Via Ollama |")
    print(f"| Vector DB | Qdrant | Collection: `{collection}` |")
    print(f"| Chunking | SentenceSplitter | 800 tokens, 200 overlap |")
    print()

    # Footer
    print("=" * 60)
    print("Copy the sections above into context/STATE.md as needed.")
    print("Don't forget to update 'Last Updated' date!")
    if not check_services:
        print()
        print("Tip: Run with --check-services to ping services.")


if __name__ == "__main__":
    main()
