"""
Intent extraction. Owned by P1.

EXPOSES:  extract_intent(message, history, profile) -> Intent

MOCK:  regex/keyword parse - fast, zero cost, zero infra.
REAL:  OpenAI extracts structured JSON matching the Intent contract. Any failure
       (missing/bad key, rate limit, network, malformed JSON) falls back to the
       mock parser automatically - flipping MOCK_MODE=false can never 500 the
       pipeline, it just prefers the real extraction when it's available.
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

# Structured output schema - OpenAI fills this; profile is added by us afterwards.
class _IntentOutput(BaseModel):
    use_case: str = ""
    budget_monthly_max: Optional[float] = None
    priority_features: list[str] = Field(default_factory=list)
    product_types: list[str] = Field(default_factory=list)
    clarification_needed: bool = False
    clarification_question: Optional[str] = None


_SYSTEM_PROMPT = """You extract shopping intent from a customer's message for a \
Telekom phone/plan/accessory shop. Fill the response schema with:

  use_case: short paraphrase of what they want
  budget_monthly_max: EUR/month number if mentioned (e.g. "under 40" -> 40), else null
  priority_features: subset of [camera, eu_roaming, gaming, 5g, unlimited]
  product_types: subset of [phone, plan, accessory]
  clarification_needed: true ONLY if message is too vague to act on at all
  clarification_question: a single short question if clarification_needed, else null

Rules:
- clarification_needed=true only if no budget, no feature, no product type, fewer than ~6 words.
- Never invent features/types not implied by the message.
"""


def extract_intent(
    message: str,
    history: list[dict],
    profile: PreferenceProfile,
    session_id: str = "",
) -> Intent:
    """Extract intent from *message* in context of *history*.

    Pass *session_id* to enable LangChain history management: the conversation
    will be loaded as proper HumanMessage/AIMessage objects directly from the
    Supabase-backed session store.  This is what keeps context alive even when
    the server restarts mid-conversation.
    """
    if MOCK_MODE:
        return _extract_mock(message, history, profile)
    try:
        return _extract_real(message, history, profile, session_id)
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

    product_types = []
    if any(w in msg for w in ["phone", "device", "smartphone"]):
        product_types.append("phone")
    if any(w in msg for w in ["plan", "tariff", "data", "sim"]):
        product_types.append("plan")
    if any(w in msg for w in ["case", "earbuds", "charger", "accessory", "accessories"]):
        product_types.append("accessory")

    # Clarification: too vague ("good and cheap" with nothing concrete)
    clarify = not features and not product_types and budget is None and len(msg.split()) < 6

    return Intent(
        use_case=message,
        budget_monthly_max=budget,
        priority_features=features,
        product_types=product_types,
        clarification_needed=clarify,
        clarification_question=(
            "Happy to help! Is this mainly for calls and messaging, or do you also want "
            "a strong camera, gaming, or lots of data? And what monthly budget works for you?"
            if clarify else None
        ),
        profile=profile,
    )


def _extract_real(
    message: str,
    history: list[dict],
    profile: PreferenceProfile,
    session_id: str = "",
) -> Intent:
    """Real extraction via openai's native Pydantic structured output.

    Uses client.beta.chat.completions.parse(response_format=_IntentOutput)
    instead of fragile json.loads(), and loads multi-turn context from the
    Supabase-backed SessionChatHistory (LangChain BaseChatMessageHistory) so
    history survives server restarts and device switches.
    """
    from openai import OpenAI

    from app.agents.history import session_history, to_lc_message
    from app.config import OPENAI_API_KEY, OPENAI_MODEL

    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set")

    # Load history as LangChain messages from Supabase, then convert to openai dicts
    if session_id:
        from langchain_core.messages import AIMessage
        lc_past = session_history(session_id).messages[-6:]
        past_dicts = [
            {"role": "assistant" if isinstance(m, AIMessage) else "user", "content": m.content}
            for m in lc_past
        ]
    else:
        past_dicts = history[-6:]

    messages = (
        [{"role": "system", "content": _SYSTEM_PROMPT}]
        + past_dicts
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

    return Intent(
        use_case=result.use_case or message,
        budget_monthly_max=result.budget_monthly_max or profile.budget_monthly_max,
        priority_features=[f for f in result.priority_features if f in valid_features],
        product_types=[t for t in result.product_types if t in valid_types],
        clarification_needed=result.clarification_needed,
        clarification_question=result.clarification_question,
        profile=profile,
    )
