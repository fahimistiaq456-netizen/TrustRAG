"""Centralized, environment-driven configuration for Hallufix.

All important behaviour is configurable through ``HALLUFIX_*`` environment
variables (see ``.env.example``). Using ``pydantic-settings`` keeps a single
source of truth instead of scattering ``os.getenv`` calls throughout modules.
"""
from __future__ import annotations

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings read from environment variables / .env file."""

    model_config = SettingsConfigDict(env_prefix="HALLUFIX_", env_file=".env", extra="ignore")

    # Retrieval / vector store
    index_dir: str = "data/index"
    abstention_threshold: float = 0.25

    # Ollama
    ollama_host: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.2:3b"

    # --- Phase 1: Cross-encoder reranking ---
    reranker_enabled: bool = False
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    rerank_candidates: int = 10
    rerank_top_n: int = 5
    rerank_min_score: float = -10.0  # a very low default: do not filter by score

    # --- Phase 2: NLI verification ---
    nli_enabled: bool = False
    nli_model: str = "cross-encoder/nli-MiniLM2-L6-H768"
    nli_entailment_threshold: float = 0.70
    nli_contradiction_threshold: float = 0.70

    # --- Phase 4: Graph retrieval ---
    graph_enabled: bool = False
    graph_neighbors: int = 4  # number of adjacent nodes to expand per seed

    # --- Phase 6: Authentication / RBAC ---
    auth_enabled: bool = False
    jwt_secret: str = "change-me-in-production"
    access_token_expire_minutes: int = 60
    db_path: str = "data/hallufix.db"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance (reused across requests)."""
    return Settings()