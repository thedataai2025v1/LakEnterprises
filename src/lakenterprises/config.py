"""LakEnterprises settings – typed, environment-driven, provider-aware."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Optional dotenv support (may not be installed)
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv  # type: ignore

    _env_loaded = load_dotenv()
except ImportError:
    _env_loaded = False

# ---------------------------------------------------------------------------
# Provider-specific default models
# ---------------------------------------------------------------------------
_PROVIDER_DEFAULTS: dict[str, str] = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-haiku-20241022",
    "google": "gemini-1.5-flash",
    "azure": "gpt-4o-mini",
    "ollama": "llama3.1",
    "groq": "llama-3.1-8b-instant",
    "cohere": "command-r",
    "watsonx": "ibm/granite-13b-instruct",
    "fake": "fake",
}

# Provider-default embedding models
_PROVIDER_EMBEDDING_DEFAULTS: dict[str, str] = {
    "openai": "text-embedding-3-small",
    "anthropic": "none",
    "google": "text-embedding-004",
    "azure": "text-embedding-3-small",
    "ollama": "nomic-embed-text",
    "groq": "none",
    "cohere": "embed-multilingual-v3",
    "watsonx": "ibm/slate-30m-english",
    "fake": "fake",
}

# Providers that need an API key
_CLOUD_PROVIDERS = frozenset({"openai", "anthropic", "google", "azure", "groq", "cohere", "watsonx"})

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _env(key: str, default: str = "") -> str:
    """Return the environment variable *key*, falling back to *default*."""
    return os.environ.get(key, default)


def _env_bool(key: str, default: bool = False) -> bool:
    val = os.environ.get(key, str(default))
    return val.lower() in {"true", "1", "yes", "on"}


def _env_int(key: str, default: int = 0) -> int:
    try:
        return int(os.environ.get(key, str(default)))
    except (ValueError, TypeError):
        return default


# ---------------------------------------------------------------------------
# Settings class
# ---------------------------------------------------------------------------

class Settings:
    """Lazy, typed configuration for the LakEnterprises knowledge platform.

    Every property reads from ``os.environ`` with a sensible default so the
    package can be imported without any environment setup.  Call :meth:`validate`
    before starting any LLM-backed work.
    """

    # ── LLM provider ──────────────────────────────────────────────────────
    @property
    def llm_provider(self) -> str:
        return _env("LLM_PROVIDER", "openai").lower()

    @property
    def llm_model(self) -> str:
        explicit = _env("LLM_MODEL")
        if explicit:
            return explicit
        return _PROVIDER_DEFAULTS.get(self.llm_provider, _PROVIDER_DEFAULTS["openai"])

    @property
    def llm_temperature(self) -> float:
        try:
            return float(os.environ.get("LLM_TEMPERATURE", "0.0"))
        except (ValueError, TypeError):
            return 0.0

    @property
    def llm_max_tokens(self) -> int:
        return _env_int("LLM_MAX_TOKENS", 4096)

    # ── Embeddings ────────────────────────────────────────────────────────
    @property
    def embedding_model(self) -> str:
        explicit = _env("EMBEDDING_MODEL")
        if explicit:
            return explicit
        return _PROVIDER_EMBEDDING_DEFAULTS.get(
            self.llm_provider, _PROVIDER_EMBEDDING_DEFAULTS["openai"]
        )

    @property
    def embedding_dimension(self) -> int:
        return _env_int("EMBEDDING_DIMENSION", 1536)

    # ── Vector store ──────────────────────────────────────────────────────
    @property
    def vector_store_path(self) -> Path:
        return Path(_env("VECTOR_STORE_PATH", "data/vector_store"))

    @property
    def vector_store_type(self) -> str:
        return _env("VECTOR_STORE", "chroma").lower()

    # ── Database ──────────────────────────────────────────────────────────
    @property
    def db_path(self) -> Path:
        return Path(_env("DB_PATH", "data/enterprise.db"))

    @property
    def db_url(self) -> str:
        """Full SQLAlchemy-style URL (sqlite by default)."""
        explicit = _env("DATABASE_URL")
        if explicit:
            return explicit
        return f"sqlite:///{self.db_path}"

    # ── Graph database (Neo4j) ────────────────────────────────────────────
    @property
    def graph_uri(self) -> str:
        return _env("GRAPH_URI", "bolt://localhost:7687")

    @property
    def graph_user(self) -> str:
        return _env("GRAPH_USER", "neo4j")

    @property
    def graph_password(self) -> Optional[str]:
        val = _env("GRAPH_PASSWORD")
        return val or None

    @property
    def graph_store_type(self) -> str:
        return _env("GRAPH_STORE", "neo4j").lower()

    # ── RAG / retrieval ───────────────────────────────────────────────────
    @property
    def retrieval_top_k(self) -> int:
        return _env_int("RETRIEVAL_TOP_K", 5)

    @property
    def rerank_model(self) -> str:
        return _env("RERANK_MODEL", "none").lower()

    @property
    def max_subquestions(self) -> int:
        return _env_int("MAX_SUBQUESTIONS", 4)

    @property
    def max_corrective_rounds(self) -> int:
        return _env_int("MAX_CORRECTIVE_ROUNDS", 1)

    # ── Logging ───────────────────────────────────────────────────────────
    @property
    def log_level(self) -> str:
        return _env("LOG_LEVEL", "INFO").upper()

    @property
    def log_format(self) -> str:
        return _env("LOG_FORMAT", "text").lower()

    # ── Rate limiting ─────────────────────────────────────────────────────
    @property
    def rate_limit_per_minute(self) -> int:
        return _env_int("RATE_LIMIT_PER_MINUTE", 120)

    # ── Upload limits ─────────────────────────────────────────────────────
    @property
    def max_upload_mb(self) -> int:
        return _env_int("MAX_UPLOAD_MB", 5)

    # ── Cache / Redis ─────────────────────────────────────────────────────
    @property
    def cache_store(self) -> str:
        return _env("CACHE_STORE", "redis").lower()

    @property
    def redis_url(self) -> str:
        return _env("REDIS_URL", "redis://localhost:6379/0")

    # ── API keys (provider-specific) ──────────────────────────────────────
    @property
    def openai_api_key(self) -> Optional[str]:
        return _env("OPENAI_API_KEY") or None

    @property
    def anthropic_api_key(self) -> Optional[str]:
        return _env("ANTHROPIC_API_KEY") or None

    @property
    def google_api_key(self) -> Optional[str]:
        return _env("GOOGLE_API_KEY") or None

    @property
    def azure_openai_api_key(self) -> Optional[str]:
        return _env("AZURE_OPENAI_API_KEY") or None

    @property
    def azure_openai_endpoint(self) -> Optional[str]:
        return _env("AZURE_OPENAI_ENDPOINT") or None

    @property
    def azure_openai_api_version(self) -> str:
        return _env("AZURE_OPENAI_API_VERSION", "2024-10-01-preview")

    @property
    def groq_api_key(self) -> Optional[str]:
        return _env("GROQ_API_KEY") or None

    @property
    def cohere_api_key(self) -> Optional[str]:
        return _env("COHERE_API_KEY") or None

    @property
    def watsonx_apikey(self) -> Optional[str]:
        return _env("WATSONX_APIKEY") or None

    @property
    def watsonx_url(self) -> Optional[str]:
        return _env("WATSONX_URL") or None

    # ── Ollama ────────────────────────────────────────────────────────────
    @property
    def ollama_base_url(self) -> str:
        return _env("OLLAMA_BASE_URL", "http://localhost:11434")

    # ── Security / auth ──────────────────────────────────────────────────
    @property
    def jwt_secret(self) -> Optional[str]:
        return _env("JWT_SECRET") or None

    @property
    def jwt_algorithm(self) -> str:
        return _env("JWT_ALGORITHM", "HS256")

    @property
    def jwt_expiry_minutes(self) -> int:
        return _env_int("JWT_EXPIRY_MINUTES", 60)

    # ── Feature flags ─────────────────────────────────────────────────────
    @property
    def debug_mode(self) -> bool:
        return _env_bool("DEBUG", False)

    @property
    def enable_graphrag(self) -> bool:
        return _env_bool("ENABLE_GRAPH_RAG", False)

    @property
    def enable_guardrails(self) -> bool:
        return _env_bool("ENABLE_GUARDRAILS", True)

    # ── API server ────────────────────────────────────────────────────────
    @property
    def api_host(self) -> str:
        return _env("API_HOST", "0.0.0.0")

    @property
    def api_port(self) -> int:
        return _env_int("API_PORT", 8001)

    # ── Validation ────────────────────────────────────────────────────────
    def validate(self) -> None:
        """Raise ``ValueError`` if required configuration is missing.

        Cloud LLM providers require their respective API key.  Neo4j
        (when *not* using an in-memory store) requires a password.
        """
        errors: list[str] = []
        provider = self.llm_provider

        # Cloud provider API keys
        key_map: dict[str, tuple[str, Optional[str]]] = {
            "openai": ("OpenAI API key", self.openai_api_key),
            "anthropic": ("Anthropic API key", self.anthropic_api_key),
            "google": ("Google (Gemini) API key", self.google_api_key),
            "azure": ("Azure OpenAI API key", self.azure_openai_api_key),
            "groq": ("Groq API key", self.groq_api_key),
            "cohere": ("Cohere API key", self.cohere_api_key),
            "watsonx": ("Watsonx API key", self.watsonx_apikey),
        }

        if provider in _CLOUD_PROVIDERS:
            label, key = key_map.get(provider, ("", None))
            if not key:
                errors.append(f"{label} is required for provider '{provider}'")

        if provider == "azure":
            if not self.azure_openai_endpoint:
                errors.append("AZURE_OPENAI_ENDPOINT is required for Azure provider")

        if provider == "watsonx":
            if not self.watsonx_url:
                errors.append("WATSONX_URL is required for Watsonx provider")

        # Graph database
        if self.graph_store_type not in {"memory", "neo4j"}:
            errors.append(
                f"GRAPH_STORE must be 'memory' or 'neo4j', got '{self.graph_store_type}'"
            )
        if self.graph_store_type == "neo4j" and not self.graph_password:
            errors.append("GRAPH_PASSWORD is required when GRAPH_STORE=neo4j")

        if errors:
            raise ValueError("Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors))

    # ── Representation ────────────────────────────────────────────────────
    def __str__(self) -> str:
        lines = [
            f"LLM provider : {self.llm_provider}",
            f"LLM model    : {self.llm_model}",
            f"Embedding    : {self.embedding_model}",
            f"Vector store : {self.vector_store_path} ({self.vector_store_type})",
            f"Database     : {self.db_url}",
            f"Graph store  : {self.graph_store_type} ({self.graph_uri})",
            f"Top-K        : {self.retrieval_top_k}",
            f"Rerank       : {self.rerank_model}",
            f"Log level    : {self.log_level}",
            f"Log format   : {self.log_format}",
        ]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Singleton instance (import once, use everywhere)
# ---------------------------------------------------------------------------
settings = Settings()


def get_settings() -> Settings:
    """Return the (module-level) settings singleton."""
    return settings


def setup_logging() -> None:
    """Configure the root logger according to current settings."""
    fmt_map: dict[str, str] = {
        "text": "%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        "json": '{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
    }
    fmt = fmt_map.get(settings.log_format, fmt_map["text"])
    level = getattr(logging, settings.log_level, logging.INFO)
    logging.basicConfig(level=level, format=fmt, force=True)
