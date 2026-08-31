"""Catalog browse endpoints. `GET /catalog` returns the whole catalog annotated
with the session's live ranking, using the same scoring engine as chat — one
recommender in the codebase, not two."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.contracts.models import Product, QueryFilters, RankedProduct
from app.engine.eligibility import effective_filters, filter_eligible
from app.preferences.engine import decayed
from app.preferences.models import Preferences
from app.preferences.store import preference_store
from app.recommend.recommender import rank_products
from app.retrieval.catalog import get_product, load_catalog

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("", response_model=list[RankedProduct])
async def all_products(session_id: str | None = None) -> list[RankedProduct]:
    catalog = await load_catalog()
    prefs = decayed(await preference_store().get(session_id)) if session_id else Preferences()

    # Open browse: nothing is hidden. A known budget re-ranks (badges handle the
    # rest client-side), so ineligible items sink instead of disappearing.
    filters = effective_filters(QueryFilters(in_stock_only=False), prefs)
    evaluated = filter_eligible(catalog, filters, prefs)
    ranked = rank_products(evaluated, prefs)

    return [
        RankedProduct(
            **e.product.model_dump(),
            confidence=round(max(0.0, min(1.0, weighted)) * 100, 1),
            signals=signals,
            personalization_basis=basis,
        )
        for e, weighted, signals, basis in ranked
    ]


@router.get("/{product_id}", response_model=Product)
async def one_product(product_id: str) -> Product:
    product = await get_product(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="product not found")
    return product
