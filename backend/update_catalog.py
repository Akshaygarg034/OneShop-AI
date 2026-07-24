"""Sync ``data/catalog.json`` to Supabase and Qdrant.

``catalog.json`` is the only input. The legacy ``products_postgres.json`` and
``products_vector.json`` files are deliberately ignored by this command.

Every product is upserted to Supabase's ``catalog_products`` table. The same
catalog is then embedded into Qdrant, with ``image_url`` removed before any
vector document is created.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("update_catalog")

_HERE = os.path.dirname(os.path.abspath(__file__))
CATALOG_JSON = os.path.join(_HERE, "data", "catalog.json")


def load_catalog() -> list[dict]:
    """Load and validate the sole catalog source file."""
    with open(CATALOG_JSON, encoding="utf-8") as file:
        products = json.load(file)
    if not isinstance(products, list):
        raise ValueError("data/catalog.json must contain a JSON array")

    ids = [product.get("id") for product in products if isinstance(product, dict)]
    if len(ids) != len(products) or not all(isinstance(product_id, str) and product_id for product_id in ids):
        raise ValueError("Every catalog product must be an object with a non-empty string 'id'.")
    duplicates = sorted({product_id for product_id in ids if ids.count(product_id) > 1})
    if duplicates:
        raise ValueError(f"Duplicate product ids in catalog.json: {duplicates}")
    return products


def push_to_supabase(products: list[dict]) -> None:
    """Upsert the complete catalog, including display-only image_url values."""
    try:
        from dotenv import load_dotenv
        from supabase import create_client
    except ImportError as error:
        raise RuntimeError("Install backend requirements before synchronizing the catalog.") from error

    load_dotenv(os.path.join(_HERE, ".env"))
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_KEY", "")
    table = os.getenv("CATALOG_TABLE", "catalog_products")
    if not (url and key):
        raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set in backend/.env.")

    logger.info("Upserting %d products into Supabase table '%s'...", len(products), table)
    try:
        create_client(url, key).table(table).upsert(products, on_conflict="id").execute()
    except Exception as error:
        raise RuntimeError(f"Supabase upsert failed: {error}") from error


def rebuild_qdrant() -> None:
    """Rebuild Qdrant from catalog.json; ingestion strips image_url."""
    try:
        from app.rag.ingestion import ingest

        ingest(data_file=CATALOG_JSON)
    except Exception as error:
        raise RuntimeError(f"Qdrant indexing failed: {error}") from error


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync catalog.json to Supabase and Qdrant.")
    parser.add_argument(
        "--postgres-only",
        action="store_true",
        help="Upsert catalog.json to Supabase without rebuilding Qdrant.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate catalog.json and report actions without writing to either database.",
    )
    args = parser.parse_args()

    try:
        products = load_catalog()
    except (OSError, ValueError, json.JSONDecodeError) as error:
        logger.error("Could not load catalog.json: %s", error)
        return 1

    if args.dry_run:
        logger.info("Dry run: would upsert %d products to Supabase%s.", len(products),
                    "" if args.postgres_only else " and rebuild Qdrant without image_url")
        return 0

    try:
        push_to_supabase(products)
        if not args.postgres_only:
            rebuild_qdrant()
    except RuntimeError as error:
        logger.error("Catalog sync failed: %s", error)
        return 1

    logger.info("Catalog sync complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
