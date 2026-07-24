"""
Central config. SHARED.

MOCK_MODE is the key switch:
  - MOCK_MODE=true  -> everything runs on fake data, no API keys / Qdrant needed.
                       This is how the whole team starts (Checkpoint C1).
  - MOCK_MODE=false -> real Grok + Qdrant. Flip per-module as each person's real code lands.

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

# Grok / xAI (P1, P3 use this for generation)
XAI_API_KEY = os.getenv("XAI_API_KEY", "")
XAI_MODEL = os.getenv("XAI_MODEL", "grok-2-latest")

# Qdrant (P2)
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "telekom_catalog")

# Embeddings (P2) - Grok has no embeddings API, so use a local open model.
EMBED_MODEL = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

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

# Path to the catalog file (P2 owns the data).
CATALOG_PATH = os.getenv(
    "CATALOG_PATH",
    os.path.join(os.path.dirname(__file__), "..", "data", "catalog.json"),
)
