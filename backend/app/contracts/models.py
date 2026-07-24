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
    popularity: float = 0.5             # merchandising-curated prior in [0,1]. Used ONLY to
                                         # break ties when we have no personalization signal yet
                                         # (cold start) - in production this would be a real
                                         # "recent sales velocity" metric refreshed by an offline
                                         # job, never a stand-in for eligibility or a fake ML score.


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
    brand: Optional[str] = None          # explicit brand ask (e.g. "Apple") -> HARD filter
    priority_features: list[str] = Field(default_factory=list)
    product_types: list[str] = Field(default_factory=list)  # explicit type ask -> HARD filter
    is_shopping_related: bool = True
    is_greeting: bool = False            # bare "hi"/"hello" - gets a welcome reply, not a search
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
    confidence: float = 0.0             # 0-100, a direct re-expression of `signals` below -
                                         # never a separate invented metric or fake model name.
    signals: dict[str, float] = Field(default_factory=dict)   # named contributions that were
                                         # weighted-summed into `score`: relevance / preference /
                                         # budget / popularity. This is what backs an honest
                                         # "why this?" panel - real numbers, not marketing copy.
    personalization_basis: str = "cold_start"   # "cold_start" (no profile signal yet - ranked by
                                         # retrieval relevance + merchandising prior) or
                                         # "personalized" (biased by this user's learned profile).


class RankedProduct(Product):
    """A catalog product annotated with this session's live ranking, for the
    browse view. Same scoring engine as chat recommendations
    (recommend.rank_products), just applied to the whole catalog instead of
    the top 3 - one recommendation engine in the codebase, not two."""
    confidence: float = 0.0
    signals: dict[str, float] = Field(default_factory=dict)
    personalization_basis: str = "cold_start"
    why: str = ""


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


class SessionProfileResponse(BaseModel):
    """The preference profile the assistant has learned for this session/user -
    exposed so personalization is visible and testable."""
    session_id: str
    profile: PreferenceProfile = Field(default_factory=PreferenceProfile)


class ChatResponse(BaseModel):
    """The one object the /chat endpoint returns. The whole app depends on this."""
    reply_text: str
    recommendations: list[Recommendation] = Field(default_factory=list)
    nba: list[str] = Field(default_factory=list)          # next-best-action nudges
    cart: Cart
    receipts: Receipts = Field(default_factory=Receipts)
    conversation_id: str = ""                              # echoed back so client can track the thread
