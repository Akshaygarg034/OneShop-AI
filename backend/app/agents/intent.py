"""
Intent extraction. Owned by P1.

EXPOSES:  extract_intent(message, history, profile) -> Intent

MOCK:  regex/keyword parse - fast, zero cost, zero infra.
REAL:  OpenAI extracts structured JSON matching the Intent contract. Any failure
       (missing/bad key, rate limit, network, malformed JSON) falls back to the
       mock parser automatically - flipping MOCK_MODE=false can never 500 the
       pipeline, it just prefers the real extraction when it's available.

`history` is the CURRENT conversation thread's turns (passed in by the
orchestrator), already loaded fresh from the persisted session - so multi-turn
context survives restarts without bleeding across unrelated threads.
"""
import logging
import re
from typing import Optional

from pydantic import BaseModel, Field

from app.config import MOCK_MODE
from app.contracts.models import Intent, PreferenceProfile

logger = logging.getLogger(__name__)

# Simple feature keyword map for the mock.
_FEATURE_WORDS = {
    "camera": ["camera", "photo", "photos", "picture"],
    "eu_roaming": ["travel", "roaming", "europe", "abroad"],
    "gaming": ["gaming", "game", "games"],
    "5g": ["5g", "fast internet"],
    "unlimited": ["unlimited", "lots of data", "stream", "streaming"],
}

# Map the words a customer uses to the canonical brand names in the catalog.
_BRAND_WORDS = {
    "Apple": ["apple", "iphone", "ios"],
    "Samsung": ["samsung", "galaxy"],
    "Google": ["google", "pixel"],
    "Telekom": ["telekom", "magenta"],
}
_VALID_BRANDS = set(_BRAND_WORDS.keys())


def _canonical_brand(raw: Optional[str]) -> Optional[str]:
    """Normalise a free-text brand ('iPhone', 'galaxy') to a catalog brand."""
    if not raw:
        return None
    low = raw.strip().lower()
    for canon, words in _BRAND_WORDS.items():
        if low == canon.lower() or any(w in low for w in words):
            return canon
    return None


# Structured output schema - OpenAI fills this; profile is added by us afterwards.
class _IntentOutput(BaseModel):
    use_case: str = ""
    budget_monthly_max: Optional[float] = None
    brand: Optional[str] = None
    priority_features: list[str] = Field(default_factory=list)
    product_types: list[str] = Field(default_factory=list)
    is_shopping_related: bool = True
    clarification_needed: bool = False
    clarification_question: Optional[str] = None


_SYSTEM_PROMPT = """You extract shopping intent from a customer's message for a \
Telekom phone/plan/accessory shop. Fill the response schema with:

  use_case: short paraphrase of what they want
  budget_monthly_max: EUR/month number if mentioned (e.g. "under 40" -> 40), else null
  brand: the canonical brand IF the customer names a specific brand or model -
         one of [Apple, Samsung, Google, Telekom] (map "iPhone"->Apple,
         "Galaxy"->Samsung, "Pixel"->Google), else null
  priority_features: subset of [camera, eu_roaming, gaming, 5g, unlimited]
  product_types: subset of [phone, plan, accessory]
  is_shopping_related: false when the customer is asking about something outside
         shopping for Telekom phones, plans, bundles, or accessories. In that
         case, do not extract a product preference.
  clarification_needed: true ONLY if message is too vague to act on at all
  clarification_question: a single short question if clarification_needed, else null

Rules:
- clarification_needed=true only if no budget, no brand, no feature, no product type, fewer than ~6 words.
- Set brand ONLY when the customer explicitly names one; never guess a brand from features.
- Never invent features/types not implied by the message.
- General knowledge, entertainment, homework, weather, coding, and other
  unrelated requests are not shopping-related.
"""

_SHOPPING_WORDS = {
    "accessories", "accessory", "apple", "budget", "buy", "camera", "case",
    "charger", "data plan", "earbuds", "galaxy", "google", "iphone", "magenta",
    "gaming", "phone", "pixel", "plan", "price", "roaming", "samsung", "sim",
    "smartphone", "streaming", "tariff", "telekom", "travel", "unlimited", "5g",
}
_NON_SHOPPING_PATTERNS = (
    r"\b(tell|make|write)\b.*\b(joke|poem|story|recipe)\b",
    r"\b(weather|forecast|capital of|president|homework|math problem|python code)\b",
    r"\bwho (is|was|invented)\b",
)


def _is_shopping_related(message: str, history: list[dict]) -> bool:
    """Keep unrelated requests out of the product retrieval pipeline.

    A short follow-up such as "under 30" is accepted only when this conversation
    already contains a shopping request. Explicitly unrelated questions always
    remain out of scope, even in a shopping conversation.
    """
    msg = message.lower()
    if any(re.search(pattern, msg) for pattern in _NON_SHOPPING_PATTERNS):
        return False
    if any(word in msg for word in _SHOPPING_WORDS):
        return True
    # Keep genuinely vague messages in the existing clarification flow instead
    # of treating them as an unrelated question.
    if len(msg.split()) <= 3:
        return True
    has_shopping_context = any(
        turn.get("role") == "user" and any(word in turn.get("content", "").lower() for word in _SHOPPING_WORDS)
        for turn in history
    )
    return has_shopping_context and bool(re.search(r"\b(under|below|max|cheaper|more|less|that|this|it|one)\b|\d", msg))


def extract_intent(message: str, history: list[dict], profile: PreferenceProfile) -> Intent:
    if MOCK_MODE:
        return _extract_mock(message, history, profile)
    try:
        return _extract_real(message, history, profile)
    except Exception as e:  # noqa - real extraction must never crash the pipeline
        logger.warning("OpenAI intent extraction failed (%s); falling back to mock parsing.", e)
        return _extract_mock(message, history, profile)


def _extract_mock(message: str, history: list[dict], profile: PreferenceProfile) -> Intent:
    msg = message.lower()

    # budget: find "40 euro", "under 30", "€25"
    budget = profile.budget_monthly_max
    m = re.search(r"(?:under|below|max|€|eur|euro[s]?)\D{0,6}(\d{1,4})", msg)
    if not m:
        m = re.search(r"(\d{1,4})\s*(?:€|eur|euro)", msg)
    if m:
        budget = float(m.group(1))

    features = [feat for feat, words in _FEATURE_WORDS.items() if any(w in msg for w in words)]

    brand = None
    for canon, words in _BRAND_WORDS.items():
        if any(w in msg for w in words):
            brand = canon
            break

    product_types = []
    if any(w in msg for w in ["phone", "device", "smartphone"]):
        product_types.append("phone")
    if any(w in msg for w in ["plan", "tariff", "data", "sim"]):
        product_types.append("plan")
    if any(w in msg for w in ["case", "earbuds", "charger", "accessory", "accessories"]):
        product_types.append("accessory")

    # Clarification: too vague ("good and cheap" with nothing concrete)
    clarify = (
        not features and not product_types and not brand
        and budget is None and len(msg.split()) < 6
    )

    return Intent(
        use_case=message,
        budget_monthly_max=budget,
        brand=brand,
        priority_features=features,
        product_types=product_types,
        is_shopping_related=_is_shopping_related(message, history),
        clarification_needed=clarify,
        clarification_question=(
            "Happy to help! Is this mainly for calls and messaging, or do you also want "
            "a strong camera, gaming, or lots of data? And what monthly budget works for you?"
            if clarify else None
        ),
        profile=profile,
    )


def _extract_real(message: str, history: list[dict], profile: PreferenceProfile) -> Intent:
    """Real extraction via openai's native Pydantic structured output.

    Uses client.beta.chat.completions.parse(response_format=_IntentOutput)
    instead of fragile json.loads(). `history` is the current thread's turns,
    already loaded from the persisted session by the orchestrator.
    """
    from openai import OpenAI

    from app.config import OPENAI_API_KEY, OPENAI_MODEL

    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set")

    past = [
        {"role": t.get("role", "user"), "content": t.get("content", "")}
        for t in (history[-6:] if history else [])
    ]
    messages = (
        [{"role": "system", "content": _SYSTEM_PROMPT}]
        + past
        + [{"role": "user", "content": message}]
    )

    client = OpenAI(api_key=OPENAI_API_KEY)
    resp = client.beta.chat.completions.parse(
        model=OPENAI_MODEL,
        messages=messages,
        response_format=_IntentOutput,
        temperature=0,
        timeout=15,
    )
    result: _IntentOutput = resp.choices[0].message.parsed

    valid_features = set(_FEATURE_WORDS.keys())
    valid_types = {"phone", "plan", "accessory"}
    brand = _canonical_brand(result.brand)

    return Intent(
        use_case=result.use_case or message,
        budget_monthly_max=result.budget_monthly_max or profile.budget_monthly_max,
        brand=brand,
        priority_features=[f for f in result.priority_features if f in valid_features],
        product_types=[t for t in result.product_types if t in valid_types],
        is_shopping_related=result.is_shopping_related and _is_shopping_related(message, history),
        clarification_needed=result.clarification_needed,
        clarification_question=result.clarification_question,
        profile=profile,
    )
