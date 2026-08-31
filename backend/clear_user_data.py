"""Wipe all user-generated data: carts, preferences, conversations, messages,
orders, conversation-memory vectors — and optionally the user accounts.

The product catalog (Supabase `catalog_products` + the Qdrant catalog
collection) is never touched; re-seed that with update_catalog.py.

Usage:
    python clear_user_data.py                  # asks for confirmation
    python clear_user_data.py --yes            # no prompt
    python clear_user_data.py --yes --include-users
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from app.clients import close_clients, init_clients, qdrant_client, supabase_client
from app.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("clear_user_data")

# (table, primary-key column) — PostgREST requires a filter on delete, so we
# match every row whose key differs from an impossible sentinel value.
_TABLES = [
    ("messages", "conversation_id"),
    ("conversations", "id"),
    ("user_preferences", "session_id"),
    ("sessions", "session_id"),
    ("orders", "order_id"),
]
_USERS_TABLE = ("users", "email")
_SENTINEL = "__never_matches__"


async def _clear_table(table: str, key: str) -> None:
    resp = await supabase_client().table(table).delete().neq(key, _SENTINEL).execute()
    logger.info("cleared %-16s (%d rows)", table, len(resp.data or []))


async def _clear_memory_vectors() -> None:
    from app.conversations.memory import ensure_memory_collection

    settings = get_settings()
    client = qdrant_client()
    if await client.collection_exists(settings.qdrant_memory_collection):
        await client.delete_collection(settings.qdrant_memory_collection)
    await ensure_memory_collection()
    logger.info("cleared conversation-memory vectors (%s)", settings.qdrant_memory_collection)


async def run(include_users: bool) -> int:
    settings = get_settings()
    if not settings.uses_supabase:
        logger.error("STORAGE_BACKEND=memory holds no persistent data — nothing to clear.")
        return 1

    await init_clients()
    try:
        for table, key in _TABLES:
            await _clear_table(table, key)
        if include_users:
            await _clear_table(*_USERS_TABLE)
        await _clear_memory_vectors()
    finally:
        await close_clients()

    logger.info("Done. Catalog data was left untouched.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    parser.add_argument("--include-users", action="store_true",
                        help="also delete all user accounts (default keeps them)")
    args = parser.parse_args()

    scope = "carts, preferences, conversations, messages, orders, memory vectors"
    if args.include_users:
        scope += ", AND ALL USER ACCOUNTS"
    if not args.yes:
        answer = input(f"This permanently deletes: {scope}.\nType 'yes' to continue: ").strip().lower()
        if answer != "yes":
            print("Aborted.")
            return 1

    return asyncio.run(run(args.include_users))


if __name__ == "__main__":
    sys.exit(main())
