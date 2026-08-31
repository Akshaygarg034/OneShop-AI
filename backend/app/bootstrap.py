"""Schema bootstrap: bring Postgres tables and Qdrant collections up to date at startup.

The Supabase REST client can't run DDL, so table creation needs a direct
Postgres connection (SUPABASE_DB_URL). db/schema.sql is fully idempotent —
safe to execute on every boot. Without SUPABASE_DB_URL the schema must be
applied manually once (Supabase SQL editor); we detect that and say so.
"""
from __future__ import annotations

import logging
import os

from app.config import get_settings

logger = logging.getLogger(__name__)

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "schema.sql")


async def apply_schema() -> None:
    """Execute db/schema.sql over a direct Postgres connection."""
    import asyncpg

    settings = get_settings()
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        schema_sql = f.read()

    # statement_cache_size=0 keeps this compatible with Supabase's pgbouncer pooler.
    conn = await asyncpg.connect(settings.supabase_db_url, statement_cache_size=0, timeout=20)
    try:
        await conn.execute(schema_sql)
    finally:
        await conn.close()
    logger.info("bootstrap: database schema is up to date")


async def _tables_exist() -> bool:
    """Cheap REST-level probe for the presence of the core tables."""
    from app.clients import supabase_client

    settings = get_settings()
    try:
        await supabase_client().table(settings.catalog_table).select("id").limit(1).execute()
        await supabase_client().table("conversations").select("id").limit(1).execute()
        return True
    except Exception:
        return False


async def ensure_schema() -> None:
    """Called at startup (Supabase mode only). Applies the schema when a direct
    DB connection is configured; otherwise verifies the tables exist and fails
    fast with instructions if they don't."""
    settings = get_settings()
    if settings.supabase_db_url:
        await apply_schema()
        return
    if await _tables_exist():
        return
    raise RuntimeError(
        "Database tables are missing. Either set SUPABASE_DB_URL (Supabase dashboard → "
        "Settings → Database → connection string) so the server can create them "
        "automatically, or run backend/db/schema.sql once in the Supabase SQL editor."
    )


async def ensure_vector_collections() -> None:
    """Create the Qdrant collections if they don't exist yet."""
    from app.conversations.memory import ensure_memory_collection
    from app.retrieval.ingestion import ensure_collection

    settings = get_settings()
    await ensure_collection(settings.qdrant_collection)
    await ensure_memory_collection()
