"""Load .env and build Agno Ollama Cloud model instances."""

from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv

from config import ENV_PATH, MODELS


def load_env() -> None:
    """Load book/.env and map OLLAMA → OLLAMA_API_KEY for Agno."""
    load_dotenv(ENV_PATH, override=False)
    key = os.getenv("OLLAMA_API_KEY") or os.getenv("OLLAMA")
    if key:
        os.environ["OLLAMA_API_KEY"] = key.strip()


def require_api_key() -> str:
    load_env()
    key = os.getenv("OLLAMA_API_KEY") or os.getenv("OLLAMA")
    if not key:
        raise RuntimeError(
            "Missing Ollama Cloud API key. Set OLLAMA or OLLAMA_API_KEY in book/.env"
        )
    return key.strip()


@lru_cache(maxsize=32)
def get_ollama(model_id: str):
    """Return an Agno Ollama model bound to Ollama Cloud."""
    from agno.models.ollama import Ollama

    api_key = require_api_key()
    return Ollama(id=model_id, api_key=api_key)


def model_for(role: str):
    """Resolve a named role from config.MODELS to an Ollama instance."""
    if role not in MODELS:
        raise KeyError(f"Unknown model role: {role}. Known: {sorted(MODELS)}")
    return get_ollama(MODELS[role])
