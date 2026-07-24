"""
SINGLE SOURCE OF TRUTH for all data shapes that pass between the 4 slices.

RULES:
  - Everyone imports shapes from here. Nobody invents their own.
  - Changing this file is a TEAM decision. Announce it, then everyone pulls.
  - Your AI assistant must be told: "All data must conform to these contracts."

Owned by: SHARED (agreed together in Hour 0).
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ProductType(str, Enum):
    phone = "phone"
    plan = "plan"
    accessory = "accessory"
    bundle = "bundle"


class Product(BaseModel):
    """A catalog item. Owned by P2 (data/catalog.json)."""
    id: str
    type: ProductType
    name: str
    brand: str = ""
    description: str = ""
    price_monthly: float = 0.0          # for device-on-plan / plans
    price_onetime: float = 0.0          # upfront device price
    category: str = ""
    features: list[str] = Field(default_factory=list)
    compatible_plans: list[str] = Field(default_factory=list)
    stock: int = 0                      # LIVE fact - checked, never embedded
    in_stock: bool = True
    image_url: str = ""                 # display image for the frontend


class PreferenceProfile(BaseModel):
    """Session-level learned preferences. Owned by P1, persisted by P4."""
    budget_monthly_max: Optional[float] = None
    brands_viewed: list[str] = Field(default_factory=list)
    features_mentioned: list[str] = Field(default_factory=list)
    categories_browsed: list[str] = Field(default_factory=list)
    rejected: list[str] = Field(default_factory=list)


class Intent(BaseModel):
    """Output of P1's intent step."""
    use_case: str = ""
    budget_monthly_max: Optional[float] = None
    priority_features: list[str] = Field(default_factory=list)
    product_types: list[str] = Field(default_factory=list)
    clarification_needed: bool = False
    clarification_question: Optional[str] = None
    profile: PreferenceProfile = Field(default_factory=PreferenceProfile)


class EligibleProduct(BaseModel):
    """Output of P2's deterministic eligibility engine."""
    product: Product
    eligible: bool = True
    reasons: list[str] = Field(default_factory=list)
    failed_rules: list[str] = Field(default_factory=list)


class Recommendation(BaseModel):
    """Output of P3's ranking + explanation."""
    product_id: str
    rank: int = 0
    score: float = 0.0
    why: str = ""
    bundle: list[str] = Field(default_factory=list)


class CartItem(BaseModel):
    product_id: str
    qty: int = 1
    price: float = 0.0
    name: str = ""                       # denormalised for display / omnichannel
    billing: str = "onetime"             # "onetime" (accessories) | "monthly" (phones/plans)


class Cart(BaseModel):
    """Owned by P4.

    Telekom sells one-time goods (accessories) AND monthly commitments (phones on a
    plan, tariffs). We track both:
      - subtotal:      sum of ONE-TIME item prices -> drives the free-shipping nudge.
      - monthly_total: sum of MONTHLY item prices  -> the recurring commitment.
    """
    session_id: str
    items: list[CartItem] = Field(default_factory=list)
    subtotal: float = 0.0                # one-time goods total
    monthly_total: float = 0.0           # recurring monthly total
    free_shipping_threshold: float = 50.0


class Receipts(BaseModel):
    """The 'keep receipts' trust feature - what happened this turn."""
    retrieved_ids: list[str] = Field(default_factory=list)
    rules_fired: list[str] = Field(default_factory=list)
    shown_ids: list[str] = Field(default_factory=list)


class ChatRequest(BaseModel):
    session_id: str
    message: str
    conversation_id: Optional[str] = None  # omit to start a new conversation


class ChatHistoryMessage(BaseModel):
    role: str
    content: str
    recommendations: list[dict] = Field(default_factory=list)  # persisted so product cards can be restored


class ChatHistoryResponse(BaseModel):
    """Persisted conversation for a specific conversation thread."""
    session_id: str
    conversation_id: str = ""
    history: list[ChatHistoryMessage] = Field(default_factory=list)


class ChatConversationsResponse(BaseModel):
    """List of conversation IDs under a session."""
    session_id: str
    conversation_ids: list[str] = Field(default_factory=list)


class ChatResponse(BaseModel):
    """The one object the /chat endpoint returns. The whole app depends on this."""
    reply_text: str
    recommendations: list[Recommendation] = Field(default_factory=list)
    nba: list[str] = Field(default_factory=list)          # next-best-action nudges
    cart: Cart
    receipts: Receipts = Field(default_factory=Receipts)
    conversation_id: str = ""                              # echoed back so client can track the thread
