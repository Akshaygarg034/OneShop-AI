"""
Intent extraction. Owned by P1.

EXPOSES:  extract_intent(message, history, profile) -> Intent

MOCK (now):  regex/keyword parse so the pipeline works immediately.
REAL (P1):   call Grok (ChatXAI) with a prompt that returns structured Intent JSON.
             Import langchain_xai INSIDE the real function.
"""
import re

from app.config import MOCK_MODE
from app.contracts.models import Intent, PreferenceProfile

# Simple feature keyword map for the mock.
_FEATURE_WORDS = {
    "camera": ["camera", "photo", "photos", "picture"],
    "eu_roaming": ["travel", "roaming", "europe", "abroad"],
    "gaming": ["gaming", "game", "games"],
    "5g": ["5g", "fast internet"],
    "unlimited": ["unlimited", "lots of data", "stream", "streaming"],
}


def extract_intent(message: str, history: list[dict], profile: PreferenceProfile) -> Intent:
    if MOCK_MODE:
        return _extract_mock(message, history, profile)
    return _extract_real(message, history, profile)


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
    """
    TODO (P1): call Grok via ChatXAI. Prompt it to output JSON matching the Intent
    contract (budget, priority_features, product_types, clarification_needed...).
    Parse and validate into Intent. Keep the SAME return shape as the mock.
    """
    raise NotImplementedError("P1: implement Grok intent extraction, then set MOCK_MODE=false")
