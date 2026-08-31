"""Hybrid candidate retrieval.

Semantic queries hit Qdrant with hard constraints (brand, category, price,
stock) pushed down as payload filters — so "an iPhone under €800" is filtered
inside the vector search instead of hoping the top-k happens to contain one.
Pure attribute queries ("phones with 8GB RAM") and Qdrant outages fall back to
a structured scan of the cached catalog. The eligibility engine re-verifies
every candidate against live data afterwards, so this layer only needs recall,
not precision.
"""
from __future__ import annotations

import logging

from qdrant_client import models as qm
from tenacity import retry, stop_after_attempt, wait_exponential

from app.clients import embed_texts, qdrant_client
from app.config import get_settings
from app.contracts.models import Product, QueryFilters
from app.retrieval.catalog import get_product, load_catalog
from app.retrieval.color_families import expand_colors

logger = logging.getLogger(__name__)


def _qdrant_filter(filters: QueryFilters) -> qm.Filter | None:
    must: list[qm.Condition] = []
    must_not: list[qm.Condition] = []

    if filters.in_stock_only:
        must.append(qm.FieldCondition(key="in_stock", match=qm.MatchValue(value=True)))
    if filters.product_types:
        must.append(qm.FieldCondition(key="type", match=qm.MatchAny(any=filters.product_types)))
    if filters.categories:
        must.append(qm.FieldCondition(key="category", match=qm.MatchAny(any=filters.categories)))
    if filters.subcategories:
        must.append(qm.FieldCondition(key="subcategory", match=qm.MatchAny(any=filters.subcategories)))
    if filters.brands_include:
        must.append(qm.FieldCondition(
            key="brand", match=qm.MatchAny(any=[b.lower() for b in filters.brands_include])
        ))
    if filters.brands_exclude:
        must_not.append(qm.FieldCondition(
            key="brand", match=qm.MatchAny(any=[b.lower() for b in filters.brands_exclude])
        ))
    if filters.colors:
        # Payload colors carry shade + family, so expanding the request makes
        # "lemon" find yellow-family products and vice versa.
        must.append(qm.FieldCondition(
            key="colors", match=qm.MatchAny(any=expand_colors(filters.colors))
        ))
    if filters.price_min is not None or filters.price_max is not None:
        must.append(qm.FieldCondition(
            key="effective_price",
            range=qm.Range(gte=filters.price_min, lte=filters.price_max),
        ))
    if filters.min_rating is not None:
        must.append(qm.FieldCondition(key="rating", range=qm.Range(gte=filters.min_rating)))
    if filters.on_sale_only:
        must.append(qm.FieldCondition(key="discount_pct", range=qm.Range(gt=0)))

    if not must and not must_not:
        return None
    return qm.Filter(must=must or None, must_not=must_not or None)


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=0.5, max=2), reraise=True)
async def _semantic_search(query: str, filters: QueryFilters, top_k: int) -> list[str]:
    settings = get_settings()
    vector = (await embed_texts([query]))[0]
    result = await qdrant_client().query_points(
        collection_name=settings.qdrant_collection,
        query=vector,
        query_filter=_qdrant_filter(filters),
        limit=top_k,
        with_payload=["product_id"],
    )
    return [pt.payload["product_id"] for pt in result.points if pt.payload]


def _structured_scan(catalog: list[Product], filters: QueryFilters, query: str, top_k: int) -> list[Product]:
    """Constraint-first fallback: cheap keyword affinity + popularity ordering.
    Precision is enforced later by the eligibility engine."""
    words = {w for w in query.lower().split() if len(w) > 2}

    def matches_hard(p: Product) -> bool:
        if filters.product_types and p.type.value not in filters.product_types:
            return False
        if filters.categories and p.category not in filters.categories:
            return False
        if filters.subcategories and p.subcategory not in filters.subcategories:
            return False
        if filters.brands_include and p.brand.lower() not in (b.lower() for b in filters.brands_include):
            return False
        if p.brand.lower() in (b.lower() for b in filters.brands_exclude):
            return False
        if filters.in_stock_only and not (p.in_stock and p.stock > 0):
            return False
        return True

    def score(p: Product) -> float:
        text = f"{p.name} {p.brand} {p.description} {' '.join(p.features)}".lower()
        return sum(1.0 for w in words if w in text) + p.popularity

    candidates = [p for p in catalog if matches_hard(p)]
    candidates.sort(key=score, reverse=True)
    return candidates[:top_k]


async def retrieve(filters: QueryFilters, semantic_query: str, top_k: int | None = None) -> list[Product]:
    settings = get_settings()
    top_k = top_k or settings.retrieval_top_k
    catalog = await load_catalog()

    if semantic_query.strip():
        try:
            ids = await _semantic_search(semantic_query, filters, top_k)
            products = [p for pid in ids if (p := await get_product(pid))]
            if products:
                return products
            logger.info("retrieval: semantic search returned nothing mappable; using structured scan")
        except Exception:
            logger.exception("retrieval: semantic search failed; using structured scan")

    return _structured_scan(catalog, filters, semantic_query, top_k)
