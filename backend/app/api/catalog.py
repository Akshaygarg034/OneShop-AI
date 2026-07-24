"""
Read-only catalog endpoint. Owned by P2.
The frontend uses this to render product cards (name, price, stock).

`GET /catalog` always returns RankedProduct - a Product plus this session's
live ranking (confidence/signals/why/personalization_basis), so there is one
recommendation engine for the whole app (recommend.rank_products), not a
duplicate client-side heuristic. Pass `session_id` to personalize against that
user's learned PreferenceProfile; omit it for an anonymous, cold-start-ranked
listing (still deterministic and honest, just not personalized).

The "why" here is always the deterministic template (recommend.template_why),
never an LLM call - firing OpenAI once per catalog item on every page load
would be slow and expensive for no real benefit over a template explanation.
The LLM-generated "why" is reserved for the handful of picks the chat
assistant actively recommends.
"""
from fastapi import APIRouter, HTTPException

from app.contracts.models import Intent, PreferenceProfile, Product, RankedProduct
from app.engine.eligibility import filter_eligible
from app.recommend.recommender import rank_products, template_why
from app.retrieval.catalog import get_product, load_catalog
from app.session.store import store

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("", response_model=list[RankedProduct])
def all_products(session_id: str | None = None) -> list[RankedProduct]:
    catalog = load_catalog()
    profile = store.get(session_id).profile if session_id else PreferenceProfile()

    # Open browse: no product-type/feature filter, just respect a known budget
    # (if any) so over-budget items rank lower without being hidden.
    intent = Intent(budget_monthly_max=profile.budget_monthly_max)
    evaluated = filter_eligible(catalog, intent)
    ranked = rank_products(evaluated, profile)

    return [
        RankedProduct(
            **e.product.model_dump(),
            confidence=round(max(0.0, min(1.0, weighted)) * 100, 1),
            signals=signals,
            personalization_basis=basis,
            why=template_why(e, profile, signals, basis),
        )
        for e, weighted, signals, basis in ranked
    ]


@router.get("/{product_id}", response_model=Product)
def one_product(product_id: str) -> Product:
    p = get_product(product_id)
    if not p:
        raise HTTPException(status_code=404, detail="product not found")
    return p
