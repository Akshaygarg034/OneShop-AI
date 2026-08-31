"""Structured user-preference model, persisted per session/user."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator

# Key for a budget that isn't tied to one category ("my overall budget is 500").
ANY_CATEGORY = "any"


class Affinity(BaseModel):
    score: float = 0.0          # -1..1; negative = dislike
    hard: bool = False          # True + negative score = hard exclusion (never shown)
    last_seen: str = ""         # ISO-8601 UTC


class BudgetPreference(BaseModel):
    min: Optional[float] = None
    max: Optional[float] = None
    period: Literal["onetime", "monthly"] = "onetime"
    # "stated" budgets hard-filter future queries; "inferred" (from purchases) only biases ranking.
    source: Literal["stated", "inferred"] = "stated"
    updated_at: str = ""


class Preferences(BaseModel):
    # Budgets are per category ("smartphones" -> 300-500), because a phone budget
    # says nothing about earbuds. ANY_CATEGORY holds a general fallback budget.
    budgets: dict[str, BudgetPreference] = Field(default_factory=dict)
    brands: dict[str, Affinity] = Field(default_factory=dict)
    categories: dict[str, Affinity] = Field(default_factory=dict)
    features: dict[str, Affinity] = Field(default_factory=dict)
    # Soft attribute preferences, e.g. {"ram_gb": {"min": 8}, "color": {"values": ["black"]}}.
    # Used for ranking, never as a hard filter (only this turn's explicit query filters are hard).
    attributes: dict[str, Any] = Field(default_factory=dict)
    rejected_products: dict[str, str] = Field(default_factory=dict)  # product_id -> reason
    prefers_deals: bool = False

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_budget(cls, data: Any) -> Any:
        """Older profiles stored one global `budget` — fold it into `budgets`."""
        if isinstance(data, dict) and data.get("budget") and not data.get("budgets"):
            data["budgets"] = {ANY_CATEGORY: data["budget"]}
        return data

    def budget_for(self, category: Optional[str]) -> Optional[BudgetPreference]:
        """The budget that applies when shopping `category`: the category's own
        budget if stated, else the general one. A smartphone budget never
        constrains earbuds."""
        if category and category in self.budgets:
            return self.budgets[category]
        return self.budgets.get(ANY_CATEGORY)

    def hard_excluded_brands(self) -> set[str]:
        return {b for b, a in self.brands.items() if a.hard and a.score < 0}

    def strength(self) -> int:
        """Coarse 0..3 measure of how much we know — drives cold/warm ranking weights."""
        strength = 0
        if self.budgets:
            strength += 1
        if self.features or self.attributes:
            strength += 1
        if self.brands or self.categories or self.rejected_products:
            strength += 1
        return strength


class PreferenceDelta(BaseModel):
    """One preference change extracted from a user message by the LLM."""
    target: Literal["brand", "category", "feature", "attribute", "budget", "product", "deals"]
    action: Literal["like", "dislike", "exclude", "retract", "set"]
    key: str = ""                      # brand/category/feature/attribute name or product id
    number_min: Optional[float] = None  # budget min or attribute lower bound
    number_max: Optional[float] = None  # budget max or attribute upper bound
    values: Optional[list[str]] = None  # attribute values, e.g. ["black", "blue"]
    period: Optional[Literal["onetime", "monthly"]] = None  # budget billing period
    reason: str = ""
