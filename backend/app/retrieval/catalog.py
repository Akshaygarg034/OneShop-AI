"""
Catalog loader. Owned by P2.
Loads data/catalog.json into Product objects. Cached in memory.
"""
import json
from functools import lru_cache

from app.config import CATALOG_PATH
from app.contracts.models import Product


@lru_cache(maxsize=1)
def load_catalog() -> list[Product]:
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return [Product(**item) for item in raw]


def get_product(product_id: str) -> Product | None:
    for p in load_catalog():
        if p.id == product_id:
            return p
    return None
