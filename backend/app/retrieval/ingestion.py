"""Embed the product catalog into Qdrant, idempotently.

Point IDs are derived from product ids (uuid5), so re-running upserts in place
instead of rebuilding the collection — no downtime, no duplicate vectors.
Payload carries the filterable facts (brand, category, price, stock) so
constraints are pushed down into the vector search instead of post-filtering.
"""
from __future__ import annotations

import logging
import uuid

from qdrant_client import models as qm

from app.clients import embed_texts, qdrant_client
from app.config import get_settings
from app.contracts.models import Product
from app.retrieval.color_families import expand_colors

logger = logging.getLogger(__name__)

_NAMESPACE = uuid.UUID("2f1d4c6e-8b3a-4f5d-9c7e-1a2b3c4d5e6f")


def point_id(product_id: str) -> str:
    return str(uuid.uuid5(_NAMESPACE, product_id))


def embedding_text(p: Product) -> str:
    """The semantic document for a product: descriptive facts only (no price/stock,
    which are volatile and live in Postgres)."""
    parts = [
        f"{p.name} by {p.brand}." if p.brand else f"{p.name}.",
        f"Category: {p.category} ({p.subcategory.replace('_', ' ')})." if p.subcategory else f"Category: {p.category}.",
        p.description,
    ]
    if p.features:
        parts.append("Features: " + ", ".join(p.features) + ".")
    if p.attributes:
        specs = ", ".join(f"{k}: {v}" for k, v in p.attributes.items() if not isinstance(v, (dict, list)))
        if specs:
            parts.append("Specs: " + specs + ".")
    if p.colors:
        parts.append("Colors: " + ", ".join(p.colors) + ".")
    return " ".join(s for s in parts if s).strip()


def payload(p: Product) -> dict:
    return {
        "product_id": p.id,
        "type": p.type.value,
        "category": p.category,
        "subcategory": p.subcategory,
        "brand": p.brand.lower(),
        "effective_price": p.effective_price,
        "in_stock": p.in_stock and p.stock > 0,
        "rating": p.rating,
        "discount_pct": p.discount_pct,
        # Shades + families so "yellow" matches a "lemon" phone in the pushed-down filter.
        "colors": expand_colors(p.colors),
        "features": p.features,
    }


# Qdrant Cloud requires a payload index for every field used in a filter.
_PAYLOAD_INDEXES: dict[str, qm.PayloadSchemaType] = {
    "type": qm.PayloadSchemaType.KEYWORD,
    "category": qm.PayloadSchemaType.KEYWORD,
    "subcategory": qm.PayloadSchemaType.KEYWORD,
    "brand": qm.PayloadSchemaType.KEYWORD,
    "colors": qm.PayloadSchemaType.KEYWORD,
    "in_stock": qm.PayloadSchemaType.BOOL,
    "effective_price": qm.PayloadSchemaType.FLOAT,
    "rating": qm.PayloadSchemaType.FLOAT,
    "discount_pct": qm.PayloadSchemaType.INTEGER,
}


async def ensure_collection(name: str) -> None:
    settings = get_settings()
    client = qdrant_client()
    if not await client.collection_exists(name):
        await client.create_collection(
            collection_name=name,
            vectors_config=qm.VectorParams(size=settings.embed_dimensions, distance=qm.Distance.COSINE),
        )
    for field, schema in _PAYLOAD_INDEXES.items():
        try:
            await client.create_payload_index(collection_name=name, field_name=field, field_schema=schema)
        except Exception:
            logger.debug("ingestion: payload index %s already exists on %s", field, name)


async def ingest_catalog(products: list[Product]) -> int:
    """Upsert all products; remove vectors for products no longer in the catalog."""
    settings = get_settings()
    client = qdrant_client()
    await ensure_collection(settings.qdrant_collection)

    vectors = await embed_texts([embedding_text(p) for p in products])
    points = [
        qm.PointStruct(id=point_id(p.id), vector=vec, payload=payload(p))
        for p, vec in zip(products, vectors)
    ]
    await client.upsert(collection_name=settings.qdrant_collection, points=points)

    current_ids = {point_id(p.id) for p in products}
    stale: list[str] = []
    offset = None
    while True:
        records, offset = await client.scroll(
            collection_name=settings.qdrant_collection,
            with_payload=False,
            with_vectors=False,
            limit=256,
            offset=offset,
        )
        stale.extend(str(r.id) for r in records if str(r.id) not in current_ids)
        if offset is None:
            break
    if stale:
        await client.delete(
            collection_name=settings.qdrant_collection,
            points_selector=qm.PointIdsList(points=stale),
        )
        logger.info("ingestion: removed %d stale vectors", len(stale))

    logger.info("ingestion: upserted %d products into '%s'", len(points), settings.qdrant_collection)
    return len(points)
