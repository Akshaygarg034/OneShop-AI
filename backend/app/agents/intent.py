"""
Intent extraction. Owned by P1.

EXPOSES:  extract_intent(message, history, profile) -> Intent

MOCK:  regex/keyword parse - fast, zero cost, zero infra.
REAL:  OpenAI extracts structured JSON matching the Intent contract. Any failure
       (missing/bad key, rate limit, network, malformed JSON) falls back to the
       mock parser automatically - flipping MOCK_MODE=false can never 500 the
       pipeline, it just prefers the real extraction when it's available.
"""
import json
import logging
import re

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

_SYSTEM_PROMPT = """You extract shopping intent from a customer's message for a \
Telekom phone/plan/accessory shop. Reply with ONLY a JSON object, no prose, \
matching exactly this shape:

{
  "use_case": "<short paraphrase of what they want>",
  "budget_monthly_max": <number or null>,
  "priority_features": [<subset of: "camera","eu_roaming","gaming","5g","unlimited">],
  "product_types": [<subset of: "phone","plan","accessory">],
  "clarification_needed": <true|false>,
  "clarification_question": "<a single short question, or null>"
}

Rules:
- clarification_needed=true ONLY if the message is too vague to act on at all
  (no budget, no feature, no product type, and fewer than ~6 words).
- budget_monthly_max is a EUR/month figure if mentioned (e.g. "under 40 euros" -> 40).
- Never invent features/types not implied by the message.
"""


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


def _extract_real(message: str, history: list[dict], profile: PreferenceProfile) -> Intent:
    from openai import OpenAI  # heavy import, kept local so mock mode needs nothing installed

    from app.config import OPENAI_API_KEY, OPENAI_MODEL

    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set")

    client = OpenAI(api_key=OPENAI_API_KEY)
    recent = history[-6:] if history else []
    context = "\n".join(f"{h['role']}: {h['content']}" for h in recent)

    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"Recent conversation:\n{context}\n\nNew message: {message}"},
        ],
        temperature=0,
        timeout=15,
    )
    data = json.loads(resp.choices[0].message.content)

    valid_features = set(_FEATURE_WORDS.keys())
    valid_types = {"phone", "plan", "accessory"}

    return Intent(
        use_case=str(data.get("use_case") or message),
        budget_monthly_max=data.get("budget_monthly_max") or profile.budget_monthly_max,
        priority_features=[f for f in (data.get("priority_features") or []) if f in valid_features],
        product_types=[t for t in (data.get("product_types") or []) if t in valid_types],
        clarification_needed=bool(data.get("clarification_needed", False)),
        clarification_question=data.get("clarification_question"),
        profile=profile,
    )
