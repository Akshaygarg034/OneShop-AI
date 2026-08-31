"""Sync data/catalog.json to Supabase and Qdrant.

Usage:
    python update_catalog.py            # upsert Supabase + reindex Qdrant
    python update_catalog.py --postgres-only
    python update_catalog.py --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from app.clients import close_clients, init_clients, supabase_client
from app.config import get_settings
from app.contracts.models import Product
from app.retrieval.catalog import load_catalog_file
from app.retrieval.ingestion import ingest_catalog

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("update_catalog")


def validate(rows: list[dict]) -> list[Product]:
    ids = [row.get("id") for row in rows]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise ValueError(f"duplicate product ids: {duplicates}")
    return [Product(**row) for row in rows]


async def run(postgres_only: bool, dry_run: bool) -> int:
    rows = load_catalog_file()
    products = validate(rows)
    logger.info("catalog.json: %d valid products", len(products))
    if dry_run:
        return 0

    await init_clients()
    try:
        from app.bootstrap import ensure_schema, ensure_vector_collections

        settings = get_settings()
        await ensure_schema()
        await ensure_vector_collections()
        await supabase_client().table(settings.catalog_table).upsert(rows, on_conflict="id").execute()
        logger.info("Supabase: upserted %d products into '%s'", len(rows), settings.catalog_table)
        if not postgres_only:
            await ingest_catalog(products)
    finally:
        await close_clients()
    logger.info("Catalog sync complete.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--postgres-only", action="store_true", help="skip the Qdrant reindex")
    parser.add_argument("--dry-run", action="store_true", help="validate catalog.json only")
    args = parser.parse_args()
    try:
        return asyncio.run(run(args.postgres_only, args.dry_run))
    except Exception:
        logger.exception("catalog sync failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
