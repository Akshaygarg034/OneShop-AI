"""Typed application settings, loaded once from the environment / .env file."""
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "development"

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    embed_model: str = "text-embedding-3-small"
    embed_dimensions: int = 256

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    qdrant_collection: str = "shop_catalog"
    qdrant_memory_collection: str = "conversation_memory"

    # Supabase (Postgres). backend "memory" is for tests/local dev only.
    storage_backend: str = "supabase"  # supabase | memory
    supabase_url: str = ""
    supabase_key: str = ""
    # Direct Postgres connection string (optional). When set, the server applies
    # db/schema.sql automatically at startup instead of requiring a manual run.
    supabase_db_url: str = ""
    catalog_table: str = "catalog_products"

    # Auth
    auth_secret: str = ""
    auth_token_ttl_seconds: int = 60 * 60 * 24 * 7
    # When true, the chat endpoints require a logged-in account (guest sessions
    # can still browse and manage a cart). When false, guests can chat and their
    # history/preferences merge into their account on login.
    require_login_for_chat: bool = True

    # CORS: comma-separated list of allowed origins.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Conversation memory tuning
    history_window: int = 10          # recent messages sent verbatim to the LLM
    summary_threshold: int = 20       # messages before older turns are folded into a summary
    memory_recall_top_k: int = 3      # semantic snippets recalled from past conversations

    # Retrieval / ranking
    retrieval_top_k: int = 24
    recommendation_count: int = 3   # default cards per turn
    max_recommendations: int = 5    # hard cap, honored when the user asks for "all"/N
    catalog_cache_ttl_seconds: int = 60

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def uses_supabase(self) -> bool:
        return self.storage_backend == "supabase"

    @model_validator(mode="after")
    def _validate_required(self) -> "Settings":
        if self.storage_backend not in ("supabase", "memory"):
            raise ValueError("STORAGE_BACKEND must be 'supabase' or 'memory'")
        if self.uses_supabase and not (self.supabase_url and self.supabase_key):
            raise ValueError("SUPABASE_URL and SUPABASE_KEY are required when STORAGE_BACKEND=supabase")
        if self.environment != "test":
            if not self.openai_api_key:
                raise ValueError("OPENAI_API_KEY is required")
            if len(self.auth_secret) < 32 or self.auth_secret == "dev-insecure-secret-change-me":
                raise ValueError("AUTH_SECRET must be a unique value of at least 32 characters")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
