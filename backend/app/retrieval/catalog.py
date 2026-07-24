"""
Catalog loader. Owned by P2.

Source of truth for product prices/stock is Postgres (Supabase table
`catalog_products`), matching the "prices live in Postgres" requirement. If that
table is unreachable or empty, we fall back to the JSON data files so the app,
the RAG mock, and the eval suite keep working with zero infrastructure.

Resolution order (first that yields products wins):
  1. Supabase `catalog_products` table (when SUPABASE_URL/KEY are set)
  2. data/catalog.json

Heavy import (supabase client) stays inside the function so nothing is needed
when running purely offline.
"""
import json
import logging
import os
from functools import lru_cache

from app.config import (
    CATALOG_BACKEND,
    CATALOG_PATH,
    CATALOG_TABLE,
    SUPABASE_KEY,
    SUPABASE_URL,
)
from app.contracts.models import Product

logger = logging.getLogger(__name__)

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
_POSTGRES_JSON = os.path.join(_DATA_DIR, "products_postgres.json")
_VECTOR_JSON = os.path.join(_DATA_DIR, "products_vector.json")

# Fields the deterministic engine/cart care about (authoritative, from Postgres).
_PRICE_FIELDS = ("type", "category", "price_monthly", "price_onetime",
                 "stock", "in_stock", "compatible_plans")
# Fields that describe the product for humans + embeddings (semantic).
_SEMANTIC_FIELDS = ("name", "brand", "description", "features", "image_url", "popularity")


def _read_json(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _merge_json_products() -> list[dict]:
    """Compatibility name for callers that now reads catalog.json directly."""
    return _read_json(CATALOG_PATH)


def _load_from_supabase() -> list[dict]:
    """Read the catalog_products table via the REST client. Returns [] on any
    problem (missing table, empty, network) so the caller can fall back."""
    if not (SUPABASE_URL and SUPABASE_KEY):
        return []
    try:
        from supabase import create_client  # heavy import, kept local

        client = create_client(SUPABASE_URL, SUPABASE_KEY)
        resp = client.table(CATALOG_TABLE).select("*").execute()
        rows = resp.data or []
        if rows:
            logger.info("catalog: loaded %d products from Supabase.", len(rows))
        return rows
    except Exception as e:  # noqa - never let the catalog read take the app down
        from app.supabase_diag import describe_supabase_error

        logger.warning("catalog: Supabase read failed, using JSON files - %s",
                       describe_supabase_error(e, SUPABASE_URL))
        return []


def _to_product(row: dict) -> Product:
    # jsonb columns can come back as JSON strings depending on the client/driver.
    def _as_list(v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return []
        return v or []

    return Product(
        id=row["id"],
        type=row.get("type", "accessory"),
        name=row.get("name", ""),
        brand=row.get("brand", ""),
        description=row.get("description", ""),
        price_monthly=float(row.get("price_monthly") or 0),
        price_onetime=float(row.get("price_onetime") or 0),
        category=row.get("category", ""),
        features=_as_list(row.get("features")),
        compatible_plans=_as_list(row.get("compatible_plans")),
        stock=int(row.get("stock") or 0),
        in_stock=bool(row.get("in_stock", True)),
        image_url=row.get("image_url", ""),
        popularity=float(row.get("popularity") if row.get("popularity") is not None else 0.5),
    )


@lru_cache(maxsize=1)
def load_catalog() -> list[Product]:
    backend = (CATALOG_BACKEND or "auto").strip().lower()

    rows: list[dict] = []
    if backend in ("auto", "postgres"):
        rows = _load_from_supabase()
    if not rows:
        rows = _merge_json_products()
        logger.info("catalog: loaded %d products from JSON files.", len(rows))

    return [_to_product(r) for r in rows]


def get_product(product_id: str) -> Product | None:
    for p in load_catalog():
        if p.id == product_id:
            return p
    return None


def refresh_catalog() -> list[Product]:
    """Drop the cache and reload (e.g. after seeding Postgres)."""
    load_catalog.cache_clear()
    return load_catalog()
