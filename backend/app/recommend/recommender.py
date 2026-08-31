"""Ranking and next-best-action engine.

Every product gets four normalized signals — relevance (retrieval order),
preference (fit against learned preferences), budget (headroom in the user's
band), quality (rating + merchandising popularity, deal-aware). Signal weights
shift from relevance/quality toward preference as the profile matures
(cold-start → warm-start). All numbers are real and explainable; nothing here
is a fabricated ML score.
"""
from __future__ import annotations

import logging

from app.contracts.models import Cart, EligibleProduct, Product, Recommendation
from app.preferences.models import Preferences
from app.retrieval.catalog import load_catalog

logger = logging.getLogger(__name__)

Scored = tuple[EligibleProduct, float, dict, str]  # (item, weighted_score, signals, basis)

# A candidate must reach this fraction of the top pick's score to be shown
# alongside it — prevents padding a confident single match with filler.
_MIN_RELATIVE_SCORE = 0.55


def _weights(strength: int) -> dict[str, float]:
    if strength == 0:
        return {"relevance": 0.50, "preference": 0.10, "budget": 0.15, "quality": 0.25}
    if strength == 1:
        return {"relevance": 0.40, "preference": 0.30, "budget": 0.15, "quality": 0.15}
    return {"relevance": 0.30, "preference": 0.45, "budget": 0.15, "quality": 0.10}


def _relevance(rank_index: int, total: int) -> float:
    if total <= 1:
        return 1.0
    return round(1.0 - (rank_index / total), 3)


def _attribute_pref_satisfied(p: Product, name: str, constraint: dict) -> bool:
    value = p.colors if name in ("color", "colors") else p.attributes.get(name)
    if value is None:
        return False
    wanted = [str(v).lower() for v in constraint.get("values", [])]
    if wanted:
        pool = {str(v).lower() for v in value} if isinstance(value, list) else {str(value).lower()}
        return bool(pool & set(wanted))
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    lo, hi = constraint.get("min"), constraint.get("max")
    return (lo is None or number >= lo) and (hi is None or number <= hi)


def _preference_fit(p: Product, prefs: Preferences) -> float:
    """-1..1; neutral 0.5 when the profile has no opinion yet."""
    if not (prefs.brands or prefs.categories or prefs.features or prefs.attributes or prefs.rejected_products):
        return 0.5

    fit = 0.0
    brand = prefs.brands.get(p.brand.lower())
    if brand:
        fit += 0.35 * brand.score
    category = prefs.categories.get(p.category.lower())
    if category:
        fit += 0.25 * category.score

    liked = {f: a.score for f, a in prefs.features.items() if a.score > 0}
    if liked:
        matched = sum(score for f, score in liked.items() if f in p.features)
        fit += 0.25 * (matched / sum(liked.values()))

    if prefs.attributes:
        satisfied = sum(
            1 for name, constraint in prefs.attributes.items()
            if isinstance(constraint, dict) and _attribute_pref_satisfied(p, name, constraint)
        )
        fit += 0.15 * (satisfied / len(prefs.attributes))

    if p.id in prefs.rejected_products:
        fit -= 0.8
    return max(-1.0, min(1.0, round(fit, 3)))


def _budget_fit(p: Product, prefs: Preferences) -> float:
    budget = prefs.budget_for(p.category)
    if budget is None or budget.max is None:
        return 0.5
    billing = "monthly" if p.is_monthly else "onetime"
    if budget.period != billing:
        return 0.5
    price = p.effective_price
    if price > budget.max:
        return 0.0
    if budget.min is not None and price < budget.min:
        return 0.3
    headroom = (budget.max - price) / budget.max
    return round(max(0.0, min(1.0, 0.5 + headroom * 0.5)), 3)


def _quality(p: Product, prefs: Preferences) -> float:
    quality = 0.6 * p.popularity + 0.4 * (p.rating / 5.0 if p.rating else 0.5)
    if prefs.prefers_deals and p.discount_pct > 0:
        quality += 0.1
    return round(min(1.0, quality), 3)


def _signals(p: Product, prefs: Preferences, rank_index: int, total: int) -> dict:
    return {
        "relevance": _relevance(rank_index, total),
        "preference": _preference_fit(p, prefs),
        "budget": _budget_fit(p, prefs),
        "quality": _quality(p, prefs),
    }


def rank_products(
    evaluated: list[EligibleProduct],
    prefs: Preferences,
    top_k: int | None = None,
) -> list[Scored]:
    """Score candidates (retrieval order = most relevant first). Handles both
    eligible-only lists (chat) and full-catalog lists including ineligible
    items (browse view, where they're down-weighted rather than hidden)."""
    total = len(evaluated)
    strength = prefs.strength()
    weights = _weights(strength)
    basis = "cold_start" if strength == 0 else "personalized"

    scored: list[Scored] = []
    for idx, e in enumerate(evaluated):
        signals = _signals(e.product, prefs, idx, total)
        weighted = round(sum(signals[k] * weights[k] for k in weights), 4)
        if not e.eligible:
            weighted = round(weighted * 0.35, 4)
        scored.append((e, weighted, signals, basis))

    scored.sort(key=lambda t: t[1], reverse=True)
    return scored[:top_k] if top_k else scored


def _diversify(scored: list[Scored], k: int, floor_ratio: float = _MIN_RELATIVE_SCORE) -> list[Scored]:
    """Greedy top-k avoiding (brand, type) near-duplicates while competitive
    alternatives exist; falls back to duplicates rather than padding with
    non-competitive items. floor_ratio=0 disables the competitiveness floor
    (used when the user explicitly asked for all/N results)."""
    if not scored:
        return []
    top_score = scored[0][1]
    floor = top_score * floor_ratio if top_score > 0 else 0.0
    pool = [scored[0]] + [s for s in scored[1:] if s[1] >= floor]

    chosen: list[Scored] = []
    seen: set[tuple[str, str]] = set()
    while pool and len(chosen) < k:
        pick_idx = next(
            (i for i, c in enumerate(pool) if (c[0].product.brand, c[0].product.type.value) not in seen),
            0,
        )
        pick = pool.pop(pick_idx)
        chosen.append(pick)
        seen.add((pick[0].product.brand, pick[0].product.type.value))
    return chosen


def _bundle_ids(p: Product) -> list[str]:
    return p.compatible_plans[:1] if p.type.value == "phone" else []


async def next_best_actions(top: list[Product], cart: Cart | None, prefs: Preferences) -> list[str]:
    """Deterministic, catalog-grounded nudges (never invented prices).
    Respects the user's brand exclusions and prefers accessories actually
    compatible with the top pick."""
    nba: list[str] = []
    excluded = prefs.hard_excluded_brands()
    if top and top[0].type.value in ("phone", "tablet"):
        pick = top[0]
        catalog = await load_catalog()

        def compatible(a: Product) -> bool:
            targets = {str(t).lower() for t in a.attributes.get("compatible_with", [])}
            return pick.id.lower() in targets or pick.brand.lower() in targets

        cases = [
            a for a in catalog
            if a.type.value == "accessory" and a.in_stock and a.stock > 0
            and a.attributes.get("accessory_type") == "case"
            and a.brand.lower() not in excluded and a.id not in prefs.rejected_products
        ]
        case = next((a for a in cases if compatible(a)), None)
        if case:
            nba.append(f"Add {case.name} for €{case.price_onetime:g} to keep it protected?")
    if cart is not None:
        remaining = cart.free_shipping_threshold - cart.subtotal
        if 0 < remaining <= 20:
            nba.append(f"You're €{remaining:g} away from free shipping.")
    return nba


async def recommend(
    eligible: list[EligibleProduct],
    prefs: Preferences,
    cart: Cart | None = None,
    count: int = 3,
    exhaustive: bool = False,
) -> tuple[list[Recommendation], list[str]]:
    """exhaustive=True returns every candidate up to `count` (user asked for
    all/N results) instead of only the competitively-scored diverse subset."""
    scored = rank_products(eligible, prefs)
    top = _diversify(scored, k=count, floor_ratio=0.0 if exhaustive else _MIN_RELATIVE_SCORE)

    recs = [
        Recommendation(
            product_id=e.product.id,
            rank=i + 1,
            score=weighted,
            bundle=_bundle_ids(e.product),
            confidence=round(max(0.0, min(1.0, weighted)) * 100, 1),
            signals=signals,
            personalization_basis=basis,
        )
        for i, (e, weighted, signals, basis) in enumerate(top)
    ]
    nba = await next_best_actions([e.product for e, _, _, _ in top], cart, prefs)
    return recs, nba
