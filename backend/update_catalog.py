"""
Catalog update utility.

What it does (in order):
  1. Merges data/products_postgres.json (prices / stock) with
     data/products_vector.json (name / description / features / image_url)
     and writes the result back to data/catalog.json (the legacy fallback).
  2. Upserts every product into the Supabase `catalog_products` table so the
     live app sees the changes immediately.

Usage
-----
  # From the backend/ directory (activate your venv first):
  python update_catalog.py               # merge JSON + push to Supabase
  python update_catalog.py --json-only   # only rebuild catalog.json, skip DB
  python update_catalog.py --db-only     # only push to DB (reads catalog.json)

Adding or editing products
--------------------------
  Edit  data/products_postgres.json  for prices / stock / compatible_plans.
  Edit  data/products_vector.json    for names / descriptions / features / images.
  Then run this script.
"""
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

# ── paths ────────────────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_DATA = os.path.join(_HERE, "data")
POSTGRES_JSON = os.path.join(_DATA, "products_postgres.json")
VECTOR_JSON   = os.path.join(_DATA, "products_vector.json")
CATALOG_JSON  = os.path.join(_DATA, "catalog.json")

# Fields owned by each source file.
_PRICE_FIELDS    = ("type", "category", "price_monthly", "price_onetime",
                    "stock", "in_stock", "compatible_plans")
_SEMANTIC_FIELDS = ("name", "brand", "description", "features", "image_url")


# ── helpers ──────────────────────────────────────────────────────────────────
def _read(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _write(path: str, data: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def merge_products() -> list[dict]:
    """Join postgres + vector JSON files on product id."""
    priced   = {p["id"]: p for p in _read(POSTGRES_JSON)}
    semantic = {p["id"]: p for p in _read(VECTOR_JSON)}

    # Warn about ids present in one file but not the other.
    only_price  = set(priced)  - set(semantic)
    only_semantic = set(semantic) - set(priced)
    if only_price:
        logger.warning("ids in products_postgres.json only (no semantic data): %s", only_price)
    if only_semantic:
        logger.warning("ids in products_vector.json only (no price data): %s", only_semantic)

    merged: list[dict] = []
    for pid, base in priced.items():
        row: dict = {"id": pid}
        row.update({k: base[k] for k in _PRICE_FIELDS if k in base})
        sem = semantic.get(pid, {})
        row.update({k: sem[k] for k in _SEMANTIC_FIELDS if k in sem})
        merged.append(row)

    return merged


# ── main steps ───────────────────────────────────────────────────────────────
def rebuild_json() -> list[dict]:
    """Rebuild catalog.json from the two source files and return the products."""
    products = merge_products()
    _write(CATALOG_JSON, products)
    logger.info("catalog.json rebuilt — %d products written to %s", len(products), CATALOG_JSON)
    return products


def push_to_supabase(products: list[dict]) -> int:
    """Upsert products into the Supabase catalog_products table.
    Returns 0 on success, 1 on failure."""
    # Load env from .env if present (works when run from backend/).
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(_HERE, ".env"))
    except ImportError:
        pass  # python-dotenv is optional here

    supabase_url = os.getenv("SUPABASE_URL", "")
    supabase_key = os.getenv("SUPABASE_KEY", "")

    if not (supabase_url and supabase_key):
        logger.error(
            "SUPABASE_URL and/or SUPABASE_KEY not set. "
            "Create backend/.env with those values or export them as env vars."
        )
        return 1

    try:
        from supabase import create_client
    except ImportError:
        logger.error("supabase-py is not installed. Run: pip install supabase")
        return 1

    catalog_table = os.getenv("CATALOG_TABLE", "catalog_products")
    client = create_client(supabase_url, supabase_key)

    logger.info("Upserting %d products into '%s'...", len(products), catalog_table)
    client.table(catalog_table).upsert(products, on_conflict="id").execute()

    # Verify row count.
    result = client.table(catalog_table).select("id").execute()
    logger.info("Done. Table now holds %d rows.", len(result.data or []))
    return 0


# ── CLI ───────────────────────────────────────────────────────────────────────
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rebuild catalog.json and/or push products to Supabase."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--json-only",
        action="store_true",
        help="Only rebuild catalog.json; skip the Supabase push.",
    )
    group.add_argument(
        "--db-only",
        action="store_true",
        help="Only push to Supabase using the current catalog.json; skip rebuild.",
    )
    args = parser.parse_args()

    if args.db_only:
        # Read catalog.json directly instead of merging the two source files.
        products = _read(CATALOG_JSON)
        logger.info("Loaded %d products from catalog.json", len(products))
        return push_to_supabase(products)

    # Default: rebuild JSON first.
    products = rebuild_json()

    if args.json_only:
        return 0

    return push_to_supabase(products)


if __name__ == "__main__":
    sys.exit(main())
