"""
Central config. SHARED.

MOCK_MODE is the key switch:
  - MOCK_MODE=true  -> everything runs on fake data, no API keys / Qdrant needed.
                       This is how the whole team starts (Checkpoint C1).
  - MOCK_MODE=false -> intent extraction + "why" explanations call OpenAI. Both
                       paths catch any failure (missing/bad key, rate limit, network,
                       malformed response) and fall back to the mock/template
                       behaviour automatically, so flipping this can never 500 the
                       app - it's "prefer real, degrade safely," not a hard switch.

Read from a .env file (see .env.example).
"""
import logging
import os

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)


def _bool(name: str, default: str = "true") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


# Global mock switch (start with everything mocked).
MOCK_MODE = _bool("MOCK_MODE", "true")

# OpenAI (intent extraction + "why" explanations). Direct openai SDK - no
# langchain wrapper, so this has no dependency conflict with the RAG stack.
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Qdrant (P2)
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "telekom_catalog")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
# Embeddings (P2) - Grok has no embeddings API, so use a local open model.
EMBED_MODEL = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
# Local directory where the downloaded model is cached. Once downloaded it is
# read from disk on every subsequent start - no internet.
#
# IMPORTANT: this must live OUTSIDE backend/ (a sibling of it, not inside it).
# `uvicorn --reload` watches the current working directory (backend/, per the
# documented run command) for file changes. sentence-transformers/huggingface_hub
# write lock files here on every embed call - if this dir were under backend/,
# every single query would touch a watched file, trigger a full server reload,
# wipe the in-process model cache (see app/rag/retriever.py's @lru_cache), and
# force the ~90MB model to reload on the very next request. That was exactly the
# "model reloads on every query" bug - fixed by moving the cache out of the
# watched tree, not by changing the caching code itself.
MODEL_CACHE_DIR = os.getenv(
    "MODEL_CACHE_DIR",
    os.path.join(os.path.dirname(__file__), "..", "..", ".model_cache"),
)

# Semantic retrieval switch, independent of MOCK_MODE so RAG can be real while
# intent/recommendation still run on their mocks. When true, retrieve() does a
# Qdrant vector search and falls back to keyword matching if Qdrant/deps are
# unavailable. Requires the RAG deps installed and the collection ingested.
RAG_ENABLED = _bool("RAG_ENABLED", "false")

# Session persistence (P4).
#   SESSION_BACKEND: auto | memory | supabase
#     auto     -> Supabase if SUPABASE_URL+KEY are set, else in-memory.
#     memory   -> always in-memory (POC default; wiped on restart).
#     supabase -> require Supabase (still falls back to memory if unreachable).
SESSION_BACKEND = os.getenv("SESSION_BACKEND", "auto")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")   # service_role key (POC: RLS disabled)

# Auth (P4). Same backend selection as sessions - Supabase `users` table if
# configured, else an in-memory store. Tokens are self-contained (hmac-signed),
# so no server-side token storage/dependency is needed.
AUTH_SECRET = os.getenv("AUTH_SECRET", "dev-insecure-secret-change-me")
AUTH_TOKEN_TTL_SECONDS = int(os.getenv("AUTH_TOKEN_TTL_SECONDS", str(60 * 60 * 24 * 7)))  # 7 days

# Path to the legacy catalog file (P2 owns the data). Used as a final fallback.
CATALOG_PATH = os.getenv(
    "CATALOG_PATH",
    os.path.join(os.path.dirname(__file__), "..", "data", "catalog.json"),
)

# Catalog source:
#   auto/postgres -> read prices/stock from the Supabase `catalog_products` table,
#                    falling back to the JSON data files if it's empty/unreachable.
#   json          -> always read the JSON files (fast, offline; used by CI/evals).
CATALOG_BACKEND = os.getenv("CATALOG_BACKEND", "auto")
CATALOG_TABLE = os.getenv("CATALOG_TABLE", "catalog_products")
