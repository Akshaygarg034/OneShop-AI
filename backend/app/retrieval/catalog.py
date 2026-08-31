"""Catalog access with a short TTL cache.

Supabase (`catalog_products`) is the source of truth for live facts (price,
stock). The TTL keeps reads fast while guaranteeing changes are visible within
`catalog_cache_ttl_seconds`. With STORAGE_BACKEND=memory (tests/offline dev)
the catalog is read from data/catalog.json instead.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any, Optional

from app.config import get_settings
from app.contracts.models import Product

logger = logging.getLogger(__name__)

CATALOG_JSON_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "catalog.json")

_cache: list[Product] = []
_index: dict[str, Product] = {}
_loaded_at: float = 0.0
_lock = asyncio.Lock()


def _as_json(value: Any, default: Any):
    """Supabase jsonb columns can arrive as JSON strings depending on the client."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return value if value is not None else default


def to_product(row: dict) -> Product:
    return Product(
        id=row["id"],
        type=row.get("type", "accessory"),
        name=row.get("name", ""),
        brand=row.get("brand", ""),
        description=row.get("description", ""),
        category=row.get("category", ""),
        subcategory=row.get("subcategory", ""),
        price_onetime=float(row.get("price_onetime") or 0),
        price_monthly=float(row.get("price_monthly") or 0),
        original_price=float(row.get("original_price") or 0),
        discount_pct=int(row.get("discount_pct") or 0),
        rating=float(row.get("rating") or 0),
        review_count=int(row.get("review_count") or 0),
        colors=_as_json(row.get("colors"), []),
        model_year=int(row.get("model_year") or 0),
        warranty_months=int(row.get("warranty_months") or 0),
        features=_as_json(row.get("features"), []),
        compatible_plans=_as_json(row.get("compatible_plans"), []),
        stock=int(row.get("stock") or 0),
        in_stock=bool(row.get("in_stock", True)),
        image_url=row.get("image_url", ""),
        popularity=float(row.get("popularity") if row.get("popularity") is not None else 0.5),
        attributes=_as_json(row.get("attributes"), {}),
    )


def load_catalog_file(path: str = CATALOG_JSON_PATH) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        rows = json.load(f)
    if not isinstance(rows, list):
        raise ValueError("catalog.json must contain a JSON array")
    return rows


async def _fetch_rows() -> list[dict]:
    settings = get_settings()
    if settings.uses_supabase:
        from app.clients import supabase_client

        resp = await supabase_client().table(settings.catalog_table).select("*").execute()
        if resp.data:
            return resp.data
        logger.warning("catalog: Supabase table %s is empty — run update_catalog.py to seed it", settings.catalog_table)
    return load_catalog_file()


async def load_catalog(force: bool = False) -> list[Product]:
    global _cache, _index, _loaded_at
    ttl = get_settings().catalog_cache_ttl_seconds
    if not force and _cache and (time.monotonic() - _loaded_at) < ttl:
        return _cache
    async with _lock:
        if not force and _cache and (time.monotonic() - _loaded_at) < ttl:
            return _cache
        rows = await _fetch_rows()
        _cache = [to_product(r) for r in rows]
        _index = {p.id: p for p in _cache}
        _loaded_at = time.monotonic()
        logger.info("catalog: loaded %d products", len(_cache))
    return _cache


async def get_product(product_id: str) -> Optional[Product]:
    await load_catalog()
    return _index.get(product_id)


async def refresh_catalog() -> list[Product]:
    return await load_catalog(force=True)
