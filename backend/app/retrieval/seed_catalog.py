"""
Seed the Supabase `catalog_products` table from the JSON data files.

Prereqs:
  1. SUPABASE_URL / SUPABASE_KEY set in backend/.env
  2. run app/retrieval/catalog_schema.sql once in the Supabase SQL editor

Run:  cd backend && python -m app.retrieval.seed_catalog

Idempotent: upserts on the `id` primary key, so re-running just refreshes rows.
"""
import logging

from app.config import CATALOG_TABLE, SUPABASE_KEY, SUPABASE_URL
from app.retrieval.catalog import _merge_json_products

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seed_catalog")


def main() -> int:
    if not (SUPABASE_URL and SUPABASE_KEY):
        logger.error("SUPABASE_URL / SUPABASE_KEY not set - nothing to seed.")
        return 1

    from supabase import create_client

    products = _merge_json_products()
    logger.info("Seeding %d products into '%s'...", len(products), CATALOG_TABLE)

    client = create_client(SUPABASE_URL, SUPABASE_KEY)
    # upsert in one call; jsonb columns accept python lists directly.
    client.table(CATALOG_TABLE).upsert(products, on_conflict="id").execute()

    count = client.table(CATALOG_TABLE).select("id").execute()
    logger.info("Done. Table now holds %d rows.", len(count.data or []))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
