"""Shared data contracts for the API and agent pipeline."""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ProductType(str, Enum):
    phone = "phone"
    tablet = "tablet"
    laptop = "laptop"
    wearable = "wearable"
    audio = "audio"
    accessory = "accessory"
    plan = "plan"
    bundle = "bundle"


# Product types billed as a recurring monthly commitment; everything else is one-time.
MONTHLY_TYPES = {ProductType.plan, ProductType.bundle}


class Product(BaseModel):
    id: str
    type: ProductType
    name: str
    brand: str = ""
    description: str = ""
    category: str = ""
    subcategory: str = ""
    price_onetime: float = 0.0
    price_monthly: float = 0.0
    original_price: float = 0.0
    discount_pct: int = 0
    rating: float = 0.0
    review_count: int = 0
    colors: list[str] = Field(default_factory=list)
    model_year: int = 0
    warranty_months: int = 0
    features: list[str] = Field(default_factory=list)
    compatible_plans: list[str] = Field(default_factory=list)
    stock: int = 0
    in_stock: bool = True
    image_url: str = ""
    popularity: float = 0.5
    attributes: dict[str, Any] = Field(default_factory=dict)

    @property
    def is_monthly(self) -> bool:
        return self.type in MONTHLY_TYPES

    @property
    def effective_price(self) -> float:
        """The price a budget constraint compares against."""
        return self.price_monthly if self.is_monthly else self.price_onetime


# Closed vocabularies, enforced in the LLM extraction schema so an off-catalog
# value ("smartphone" instead of "phone") can never silently match nothing.
ProductTypeName = Literal["phone", "tablet", "laptop", "wearable", "audio", "accessory", "plan", "bundle"]
CategoryName = Literal["smartphones", "tablets", "laptops", "wearables", "audio", "accessories", "plans", "bundles"]
# The level shoppers actually ask at: "speakers", "a smartwatch", "a phone case".
SubcategoryName = Literal[
    "smartphone", "tablet", "laptop", "smartwatch", "fitness_band",
    "earbuds", "headphones", "neckband", "speaker",
    "case", "charger", "cable", "powerbank", "screen_protector", "mount", "hub",
    "mobile_plan", "home_internet", "bundle",
]


_CATEGORIES = {"smartphones", "tablets", "laptops", "wearables", "audio", "accessories", "plans", "bundles"}

TYPE_TO_CATEGORY: dict[str, str] = {
    "phone": "smartphones", "tablet": "tablets", "laptop": "laptops", "wearable": "wearables",
    "audio": "audio", "accessory": "accessories", "plan": "plans", "bundle": "bundles",
}

SUBCATEGORY_TO_CATEGORY: dict[str, str] = {
    "smartphone": "smartphones", "tablet": "tablets", "laptop": "laptops",
    "smartwatch": "wearables", "fitness_band": "wearables",
    "earbuds": "audio", "headphones": "audio", "neckband": "audio", "speaker": "audio",
    "case": "accessories", "charger": "accessories", "cable": "accessories",
    "powerbank": "accessories", "screen_protector": "accessories", "mount": "accessories",
    "hub": "accessories", "mobile_plan": "plans", "home_internet": "plans", "bundle": "bundles",
}


def normalize_category(name: str) -> Optional[str]:
    """Map a category/subcategory/type word onto a canonical category name."""
    name = name.strip().lower()
    if name in _CATEGORIES:
        return name
    return SUBCATEGORY_TO_CATEGORY.get(name) or TYPE_TO_CATEGORY.get(name)


class AttributeConstraint(BaseModel):
    """One structured constraint extracted from the user's query,
    e.g. {name: 'ram_gb', op: 'gte', number: 8} or {name: 'color', op: 'in', values: ['black']}."""
    name: str
    op: Literal["gte", "lte", "eq", "in"]
    number: Optional[float] = None
    values: Optional[list[str]] = None


class QueryFilters(BaseModel):
    """Deterministic constraints for this turn. Enforced by the eligibility engine."""
    product_types: list[ProductTypeName] = Field(default_factory=list)
    categories: list[CategoryName] = Field(default_factory=list)
    subcategories: list[SubcategoryName] = Field(default_factory=list)
    brands_include: list[str] = Field(default_factory=list)
    brands_exclude: list[str] = Field(default_factory=list)
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    price_period: Optional[Literal["onetime", "monthly"]] = None
    colors: list[str] = Field(default_factory=list)
    attributes: list[AttributeConstraint] = Field(default_factory=list)
    min_rating: Optional[float] = None
    on_sale_only: bool = False
    in_stock_only: bool = True


class EligibleProduct(BaseModel):
    product: Product
    eligible: bool = True
    reasons: list[str] = Field(default_factory=list)
    failed_rules: list[str] = Field(default_factory=list)


class Recommendation(BaseModel):
    product_id: str
    rank: int = 0
    score: float = 0.0
    bundle: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    signals: dict[str, float] = Field(default_factory=dict)
    personalization_basis: str = "cold_start"


class RankedProduct(Product):
    """Product annotated with the session's live ranking, for the browse view."""
    confidence: float = 0.0
    signals: dict[str, float] = Field(default_factory=dict)
    personalization_basis: str = "cold_start"


class CartItem(BaseModel):
    product_id: str
    qty: int = 1
    price: float = 0.0
    name: str = ""
    billing: Literal["onetime", "monthly"] = "onetime"


class Cart(BaseModel):
    session_id: str
    items: list[CartItem] = Field(default_factory=list)
    subtotal: float = 0.0
    monthly_total: float = 0.0
    free_shipping_threshold: float = 50.0


class Receipts(BaseModel):
    """Transparency record of what happened this turn: what was retrieved,
    which deterministic rules fired, and what was actually shown."""
    retrieved_ids: list[str] = Field(default_factory=list)
    rules_fired: list[str] = Field(default_factory=list)
    shown_ids: list[str] = Field(default_factory=list)


class ChatRequest(BaseModel):
    session_id: str
    message: str
    conversation_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply_text: str
    recommendations: list[Recommendation] = Field(default_factory=list)
    products: list[Product] = Field(default_factory=list)
    nba: list[str] = Field(default_factory=list)
    cart: Cart
    receipts: Receipts = Field(default_factory=Receipts)
    conversation_id: str = ""


class ChatHistoryMessage(BaseModel):
    role: str
    content: str
    recommendations: list[dict] = Field(default_factory=list)
    created_at: str = ""


class ChatHistoryResponse(BaseModel):
    session_id: str
    conversation_id: str = ""
    history: list[ChatHistoryMessage] = Field(default_factory=list)


class ConversationSummary(BaseModel):
    id: str
    title: str = ""
    updated_at: str = ""


class ChatConversationsResponse(BaseModel):
    session_id: str
    conversation_ids: list[str] = Field(default_factory=list)
    conversations: list[ConversationSummary] = Field(default_factory=list)
