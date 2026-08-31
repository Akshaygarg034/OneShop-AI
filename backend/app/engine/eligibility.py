"""Deterministic eligibility engine — the source of truth for what is offerable.

Pure functions: same input, same output. No LLM calls. The agent can phrase
recommendations but can never offer a product these rules reject.
"""
from __future__ import annotations

from typing import Any, Optional

from app.contracts.models import (
    AttributeConstraint,
    EligibleProduct,
    Product,
    QueryFilters,
    normalize_category,
)
from app.preferences.models import Preferences
from app.retrieval.color_families import colors_match


def filters_category(filters: QueryFilters) -> Optional[str]:
    """The single category this turn is about, if determinable — used to pick
    which per-category budget applies."""
    for pool in (filters.categories, filters.subcategories, filters.product_types):
        for name in pool:
            category = normalize_category(name)
            if category:
                return category
    return None


def effective_filters(filters: QueryFilters, prefs: Preferences, browse_all: bool = False) -> QueryFilters:
    """Merge persistent preferences into this turn's filters.

    - Hard-excluded brands stay excluded across conversations, unless the user
      explicitly asked for that brand this turn (the explicit ask wins).
    - A stated budget persists until the turn provides its own price range —
      except when browsing exhaustively (browse_all): "show me all tablets"
      means the whole catalog section, not "all tablets in my budget".
      Budgets are per category: a smartphone budget never constrains earbuds.
    """
    merged = filters.model_copy(deep=True)
    include = {b.lower() for b in merged.brands_include}
    for brand in prefs.hard_excluded_brands():
        if brand not in include and brand not in (b.lower() for b in merged.brands_exclude):
            merged.brands_exclude.append(brand)

    budget = prefs.budget_for(filters_category(merged))
    if (
        not browse_all
        and merged.price_min is None and merged.price_max is None
        and budget and budget.source == "stated"
    ):
        merged.price_min = budget.min
        merged.price_max = budget.max
        merged.price_period = budget.period
    return merged


def _price_ok(p: Product, filters: QueryFilters) -> Optional[bool]:
    """None = rule not applicable (no budget, or billing period mismatch)."""
    if filters.price_min is None and filters.price_max is None:
        return None
    billing = "monthly" if p.is_monthly else "onetime"
    if filters.price_period and filters.price_period != billing:
        return None
    price = p.effective_price
    if filters.price_min is not None and price < filters.price_min:
        return False
    if filters.price_max is not None and price > filters.price_max:
        return False
    return True


def _attribute_value(p: Product, name: str) -> Any:
    if name in ("color", "colors"):
        return p.colors
    if name == "rating":
        return p.rating
    if name == "brand":
        return p.brand
    return p.attributes.get(name)


def _attribute_ok(p: Product, c: AttributeConstraint) -> bool:
    name = c.name.strip().lower()
    if name in ("color", "colors"):
        return colors_match(c.values or [], p.colors)
    value = _attribute_value(p, name)
    if value is None:
        return False
    if c.op in ("gte", "lte"):
        if c.number is None:
            return True
        try:
            number = float(value)
        except (TypeError, ValueError):
            return False
        return number >= c.number if c.op == "gte" else number <= c.number
    wanted = [v.strip().lower() for v in (c.values or [])]
    if c.op == "eq":
        if c.number is not None:
            try:
                return float(value) == c.number
            except (TypeError, ValueError):
                return False
        wanted = wanted or []
    if not wanted:
        return True
    if isinstance(value, list):
        return bool({str(v).lower() for v in value} & set(wanted))
    return str(value).lower() in wanted


def evaluate(p: Product, filters: QueryFilters, prefs: Preferences) -> EligibleProduct:
    reasons: list[str] = []
    failed: list[str] = []

    def check(passed: Optional[bool], reason: str, failure: str) -> None:
        if passed is None:
            return
        (reasons if passed else failed).append(reason if passed else failure)

    if filters.in_stock_only:
        check(p.in_stock and p.stock > 0, "in_stock", "out_of_stock")

    check(_price_ok(p, filters), "within_budget", "over_budget")

    brand = p.brand.lower()
    if filters.brands_include:
        check(brand in (b.lower() for b in filters.brands_include), "brand_match", "brand_mismatch")
    if filters.brands_exclude:
        check(brand not in (b.lower() for b in filters.brands_exclude), "brand_allowed", "brand_excluded")

    if filters.product_types:
        check(p.type.value in filters.product_types, "type_match", "wrong_type")
    if filters.categories:
        check(p.category in filters.categories, "category_match", "wrong_category")
    if filters.subcategories:
        check(p.subcategory in filters.subcategories, "subcategory_match", "wrong_subcategory")

    if filters.colors:
        check(colors_match(filters.colors, p.colors), "color_match", "color_mismatch")

    for constraint in filters.attributes:
        name = constraint.name.strip().lower()
        check(_attribute_ok(p, constraint), f"attr_{name}_ok", f"attr_{name}_failed")

    if filters.min_rating is not None:
        check(p.rating >= filters.min_rating, "rating_ok", "rating_too_low")
    if filters.on_sale_only:
        check(p.discount_pct > 0, "on_sale", "not_on_sale")

    if p.id in prefs.rejected_products:
        failed.append("rejected_by_user")

    return EligibleProduct(product=p, eligible=not failed, reasons=reasons, failed_rules=failed)


def filter_eligible(products: list[Product], filters: QueryFilters, prefs: Preferences) -> list[EligibleProduct]:
    """Evaluate every candidate, keeping rejects (with reasons) for the receipts."""
    return [evaluate(p, filters, prefs) for p in products]
