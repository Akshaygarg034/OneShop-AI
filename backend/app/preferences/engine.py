"""Preference learning: conversational deltas, behavioral events, decay, and merging."""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Literal

from app.contracts.models import Product, normalize_category
from app.preferences.models import ANY_CATEGORY, Affinity, BudgetPreference, PreferenceDelta, Preferences

# Soft affinities halve in weight every 30 days of not being reinforced.
_HALF_LIFE_DAYS = 30.0
_PRUNE_BELOW = 0.05

# Behavioral signal weights (brand, category).
_EVENT_WEIGHTS: dict[str, tuple[float, float]] = {
    "view": (0.05, 0.03),
    "cart_add": (0.25, 0.20),
    "cart_remove": (-0.05, -0.03),
    "purchase": (0.50, 0.35),
}

BehaviorEvent = Literal["view", "cart_add", "cart_remove", "purchase"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _decay_factor(last_seen: str, now: datetime) -> float:
    try:
        seen = datetime.fromisoformat(last_seen)
    except ValueError:
        return 1.0
    age_days = max(0.0, (now - seen).total_seconds() / 86400.0)
    return math.pow(0.5, age_days / _HALF_LIFE_DAYS)


def decayed(prefs: Preferences) -> Preferences:
    """Return a copy with soft affinities decayed by age. Hard exclusions,
    budget, and attribute preferences persist until explicitly retracted."""
    now = datetime.now(timezone.utc)
    result = prefs.model_copy(deep=True)
    for table in (result.brands, result.categories, result.features):
        stale: list[str] = []
        for key, affinity in table.items():
            if affinity.hard:
                continue
            affinity.score = round(affinity.score * _decay_factor(affinity.last_seen, now), 4)
            if abs(affinity.score) < _PRUNE_BELOW:
                stale.append(key)
        for key in stale:
            del table[key]
    return result


def _bump(table: dict[str, Affinity], key: str, delta: float) -> None:
    key = key.strip().lower()
    if not key:
        return
    entry = table.get(key)
    if entry is not None and entry.hard:
        return  # hard exclusions only change via explicit retraction
    score = (entry.score if entry else 0.0) + delta
    table[key] = Affinity(score=max(-1.0, min(1.0, round(score, 4))), last_seen=_now_iso())


def apply_deltas(prefs: Preferences, deltas: list[PreferenceDelta]) -> Preferences:
    """Apply LLM-extracted preference changes from the current user message."""
    for d in deltas:
        key = d.key.strip().lower()
        if d.target == "budget":
            budget_key = normalize_category(key) or ANY_CATEGORY
            if d.action == "retract" or (d.number_min is None and d.number_max is None):
                # Retracting the general budget clears everything ("ignore my budget");
                # retracting a category budget clears just that category.
                if budget_key == ANY_CATEGORY:
                    prefs.budgets = {}
                else:
                    prefs.budgets.pop(budget_key, None)
            else:
                prefs.budgets[budget_key] = BudgetPreference(
                    min=d.number_min,
                    max=d.number_max,
                    period=d.period or "onetime",
                    source="stated",
                    updated_at=_now_iso(),
                )
        elif d.target == "deals":
            prefs.prefers_deals = d.action != "retract"
        elif d.target == "attribute" and key:
            if d.action == "retract":
                prefs.attributes.pop(key, None)
            else:
                constraint: dict = {}
                if d.number_min is not None:
                    constraint["min"] = d.number_min
                if d.number_max is not None:
                    constraint["max"] = d.number_max
                if d.values:
                    constraint["values"] = [v.strip().lower() for v in d.values]
                if constraint:
                    prefs.attributes[key] = constraint
        elif d.target == "product" and key:
            if d.action == "retract":
                prefs.rejected_products.pop(key, None)
            else:
                prefs.rejected_products[key] = d.reason or d.action
        elif d.target in ("brand", "category", "feature") and key:
            table = {"brand": prefs.brands, "category": prefs.categories, "feature": prefs.features}[d.target]
            if d.action == "retract":
                table.pop(key, None)
            elif d.action == "exclude":
                table[key] = Affinity(score=-1.0, hard=True, last_seen=_now_iso())
            elif d.action == "like":
                _bump(table, key, 0.4)
            elif d.action == "dislike":
                _bump(table, key, -0.4)
    return prefs


def apply_event(prefs: Preferences, event: BehaviorEvent, product: Product) -> Preferences:
    """Fold a cart/purchase signal into the profile so behavior — not just chat —
    shapes future ranking."""
    brand_w, category_w = _EVENT_WEIGHTS[event]
    if product.brand:
        _bump(prefs.brands, product.brand, brand_w)
    if product.category:
        _bump(prefs.categories, product.category, category_w)
    if event in ("cart_add", "purchase"):
        for feature in product.features[:5]:
            _bump(prefs.features, feature, 0.1 if event == "purchase" else 0.05)

    # A purchase establishes an inferred budget band for that category,
    # but never overrides a stated one.
    if event == "purchase" and product.effective_price > 0 and product.category:
        existing = prefs.budgets.get(product.category)
        if existing is None or existing.source == "inferred":
            prefs.budgets[product.category] = BudgetPreference(
                min=None,
                max=round(product.effective_price * 1.5, 2),
                period="monthly" if product.is_monthly else "onetime",
                source="inferred",
                updated_at=_now_iso(),
            )
    return prefs


def merge(target: Preferences, guest: Preferences) -> Preferences:
    """Fold a guest profile into a logged-in user's profile. The account's
    stated budgets win; affinities keep the stronger signal."""
    for category, budget in guest.budgets.items():
        existing = target.budgets.get(category)
        if existing is None or (existing.source == "inferred" and budget.source == "stated"):
            target.budgets[category] = budget
    for name in ("brands", "categories", "features"):
        target_table: dict[str, Affinity] = getattr(target, name)
        for key, affinity in getattr(guest, name).items():
            existing = target_table.get(key)
            if existing is None or (affinity.hard and not existing.hard) or (
                not existing.hard and abs(affinity.score) > abs(existing.score)
            ):
                target_table[key] = affinity
    for key, constraint in guest.attributes.items():
        target.attributes.setdefault(key, constraint)
    target.rejected_products.update(guest.rejected_products)
    target.prefers_deals = target.prefers_deals or guest.prefers_deals
    return target
