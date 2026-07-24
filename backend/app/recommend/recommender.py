"""
Ranking + "why this" + Next-Best-Action. Owned by P3.

EXPOSES:
  rank_products(evaluated, profile, top_k=None) -> list[(EligibleProduct, score, signals, basis)]
      The single scoring engine for the whole app. Used both for the chat's top-3
      picks and for the full-catalog browse view (app/api/catalog.py) - one
      recommendation engine, not two competing heuristics.
  recommend(eligible, profile, cart) -> (list[Recommendation], list[str] nba)
      Chat-facing wrapper: ranks, diversifies to 3, and writes the "why" text.
  template_why(...) -> str
      Deterministic (no LLM) explanation, reused by the browse endpoint so we
      don't fire one OpenAI call per catalog item on every page load.

SCORING MODEL (the "quality" story):
  Every product gets FOUR independent, normalized (0..1) signals:
    relevance   - how highly retrieval ranked it for this query (position-based)
    preference  - fit against the user's learned PreferenceProfile (features/brand/rejects)
    budget      - headroom under the user's stated budget
    popularity  - a merchandising-curated prior (never a fabricated ML score)
  They're blended with WEIGHTS THAT DEPEND ON HOW MUCH WE KNOW ABOUT THE USER
  (see _weights): a brand-new/cold-start user is ranked mostly by relevance +
  popularity; a user with an established profile is ranked mostly by fit. This
  is the standard cold-start-to-warm-start pattern in production recommenders,
  scaled down to something explainable and dependency-free.

GUARDRAIL (must always hold): every Recommendation.product_id MUST be in the
eligible set the caller passed in. The LLM can phrase the "why" but can NEVER
introduce a product (enforced again, belt-and-braces, in agents/graph.py).
"""
import logging

from app.config import MOCK_MODE
from app.contracts.models import Cart, EligibleProduct, PreferenceProfile, Recommendation

logger = logging.getLogger(__name__)

Scored = tuple[EligibleProduct, float, dict, str]  # (item, weighted_score, signals, basis)


# --------------------------------------------------------------------------- #
# Signal computation                                                          #
# --------------------------------------------------------------------------- #
def _profile_strength(profile: PreferenceProfile) -> int:
    """How many distinct kinds of signal we've actually learned about this
    user (0..3). Drives whether we lean on personalization or fall back to
    relevance/popularity. Deliberately coarse - this is a routing decision,
    not a score."""
    strength = 0
    if profile.budget_monthly_max is not None:
        strength += 1
    if profile.features_mentioned:
        strength += 1
    if profile.brands_viewed or profile.rejected:
        strength += 1
    return strength


def _weights(strength: int) -> dict[str, float]:
    """Cold-start -> warm-start weight schedule. As we learn more about the
    user, personalization (preference+budget) takes over from relevance and
    the merchandising prior."""
    if strength == 0:
        return {"relevance": 0.55, "preference": 0.10, "budget": 0.15, "popularity": 0.20}
    if strength == 1:
        return {"relevance": 0.40, "preference": 0.30, "budget": 0.20, "popularity": 0.10}
    return {"relevance": 0.30, "preference": 0.45, "budget": 0.20, "popularity": 0.05}


def _relevance(rank_index: int, total: int) -> float:
    """Position-based relevance from retrieval order (`evaluated` arrives in
    the order retrieve() returned it - best match first). Rank 0 of N -> 1.0,
    decaying toward 0 for the least relevant candidate."""
    if total <= 1:
        return 1.0
    return round(1.0 - (rank_index / total), 3)


def _preference_fit(e: EligibleProduct, profile: PreferenceProfile) -> float:
    """-1..1. 0.5 (neutral) when the profile has no opinion yet - NOT 0, so an
    unscored product doesn't look actively rejected."""
    p = e.product
    has_signal = bool(profile.features_mentioned or profile.brands_viewed or profile.rejected)
    if not has_signal:
        return 0.5

    fit = 0.0
    if profile.features_mentioned:
        matched = set(profile.features_mentioned) & set(p.features)
        fit += 0.6 * (len(matched) / len(profile.features_mentioned))
    if p.brand and p.brand in profile.brands_viewed:
        fit += 0.4
    if p.brand and p.brand in profile.rejected:
        fit -= 0.8  # soft penalty, not a hard exclude - "correctable" per PROJECT_OVERVIEW.md
    return max(-1.0, min(1.0, round(fit, 3)))


def _budget_fit(e: EligibleProduct, profile: PreferenceProfile) -> float:
    """0..1. Neutral 0.5 when there's no stated budget or the product has no
    monthly price to compare (one-time accessories). Rewards comfortable
    headroom under the stated budget without over-rewarding "cheapest wins"."""
    p = e.product
    if not profile.budget_monthly_max or p.price_monthly <= 0:
        return 0.5
    if p.price_monthly > profile.budget_monthly_max:
        return 0.0  # the eligibility engine should already have dropped this for chat
    headroom = (profile.budget_monthly_max - p.price_monthly) / profile.budget_monthly_max
    return round(max(0.0, min(1.0, 0.5 + headroom * 0.5)), 3)


def _signals(e: EligibleProduct, profile: PreferenceProfile, rank_index: int, total: int) -> dict:
    return {
        "relevance": _relevance(rank_index, total),
        "preference": _preference_fit(e, profile),
        "budget": _budget_fit(e, profile),
        "popularity": round(e.product.popularity, 3),
    }


def _weighted_score(signals: dict, weights: dict, eligible: bool) -> float:
    raw = sum(signals[k] * weights[k] for k in weights)
    if not eligible:
        # Browse view lists out-of-stock/over-budget items (frontend badges them) -
        # they're never hidden, just pushed down. Chat never sees ineligible items
        # here at all (graph.py filters before calling recommend()).
        raw *= 0.35
    return round(raw, 4)


# --------------------------------------------------------------------------- #
# Ranking                                                                     #
# --------------------------------------------------------------------------- #
def rank_products(
    evaluated: list[EligibleProduct],
    profile: PreferenceProfile,
    top_k: int | None = None,
) -> list[Scored]:
    """Score every item once, most relevant first. `evaluated` may be
    eligible-only (chat) or the full catalog including ineligible items
    (browse) - both are handled the same way."""
    total = len(evaluated)
    strength = _profile_strength(profile)
    weights = _weights(strength)
    basis = "cold_start" if strength == 0 else "personalized"

    scored: list[Scored] = []
    for idx, e in enumerate(evaluated):
        signals = _signals(e, profile, idx, total)
        weighted = _weighted_score(signals, weights, e.eligible)
        scored.append((e, weighted, signals, basis))

    scored.sort(key=lambda t: t[1], reverse=True)
    return scored[:top_k] if top_k else scored


def _diversify(scored: list[Scored], k: int) -> list[Scored]:
    """Greedy top-k that avoids showing near-duplicates (same brand + type)
    while the score ranking still has room to choose - e.g. don't fill all 3
    slots with Samsung phones when a Google option is nearly as good. Falls
    back to allowing duplicates once genuinely diverse options run out, so it
    never returns fewer than min(k, len(scored))."""
    chosen: list[Scored] = []
    seen: set[tuple[str, str]] = set()
    pool = list(scored)
    while pool and len(chosen) < k:
        pick_idx = next(
            (i for i, c in enumerate(pool) if (c[0].product.brand, c[0].product.type.value) not in seen),
            0,
        )
        pick = pool.pop(pick_idx)
        chosen.append(pick)
        seen.add((pick[0].product.brand, pick[0].product.type.value))
    return chosen


# --------------------------------------------------------------------------- #
# Explanation                                                                 #
# --------------------------------------------------------------------------- #
def template_why(e: EligibleProduct, profile: PreferenceProfile, signals: dict, basis: str) -> str:
    """Deterministic, no-LLM explanation grounded in the real signal
    breakdown. Used as the LLM fallback AND as the only "why" for the browse
    view (firing an OpenAI call per catalog item on every page load would be
    slow and expensive for no real benefit over a template list explanation)."""
    p = e.product

    if basis == "cold_start":
        bits = ["one of our most popular picks in this category"]
        if signals["relevance"] >= 0.5:
            bits.append("closely matches what you just asked for")
        return f"{p.name} is {', '.join(bits)}."

    matched = set(profile.features_mentioned).intersection(p.features)
    feature_bits = []
    if "camera" in matched:
        feature_bits.append("strong camera")
    if "eu_roaming" in matched:
        feature_bits.append("EU roaming for travel")
    if "unlimited" in matched or "5g" in matched:
        feature_bits.append("fast data")
    reason = ", ".join(feature_bits) if feature_bits else "your recent preferences"

    parts = [f"{p.name} matches {reason}"]
    if profile.budget_monthly_max and p.price_monthly:
        parts.append(f"fits your €{int(profile.budget_monthly_max)}/mo budget")
    if p.brand and p.brand in profile.brands_viewed and p.brand not in profile.rejected:
        parts.append(f"you've been looking at {p.brand}")
    return ", ".join(parts) + "."


def _why(e: EligibleProduct, profile: PreferenceProfile, signals: dict, basis: str) -> str:
    if MOCK_MODE:
        return template_why(e, profile, signals, basis)
    try:
        return _why_openai(e, profile, signals, basis)
    except Exception as ex:  # noqa - one bad call must not break the recommendation
        logger.warning("OpenAI 'why' generation failed for %s (%s); using template.", e.product.id, ex)
        return template_why(e, profile, signals, basis)


# --------------------------------------------------------------------------- #
# Public entry point (chat)                                                   #
# --------------------------------------------------------------------------- #
def recommend(
    eligible: list[EligibleProduct],
    profile: PreferenceProfile,
    cart: Cart | None = None,
) -> tuple[list[Recommendation], list[str]]:
    scored = rank_products(eligible, profile)
    top = _diversify(scored, k=3)

    recs: list[Recommendation] = []
    for i, (e, weighted, signals, basis) in enumerate(top):
        confidence = round(max(0.0, min(1.0, weighted)) * 100, 1)
        recs.append(Recommendation(
            product_id=e.product.id,
            rank=i + 1,
            score=weighted,
            why=_why(e, profile, signals, basis),
            bundle=_suggest_bundle(e),
            confidence=confidence,
            signals=signals,
            personalization_basis=basis,
        ))

    nba = _next_best_actions([e for e, _, _, _ in top], cart)
    return recs, nba


def _suggest_bundle(e: EligibleProduct) -> list[str]:
    p = e.product
    bundle = []
    if p.type.value == "phone":
        if p.compatible_plans:
            bundle.append(p.compatible_plans[0])
        bundle.append("accessory_case")
    return bundle


def _next_best_actions(top: list[EligibleProduct], cart: Cart | None) -> list[str]:
    nba: list[str] = []
    if top and top[0].product.type.value == "phone":
        nba.append("Add a protective case for €15 to keep it safe?")
    if cart is not None:
        remaining = cart.free_shipping_threshold - cart.subtotal
        if 0 < remaining <= 20:
            nba.append(f"You're €{int(remaining)} away from free shipping.")
    return nba


_WHY_SYSTEM_PROMPT = """You write ONE short, warm sentence explaining why a \
product fits a Telekom shopping customer. Ground it STRICTLY in the "Product"
fields and "Signals" given - never mention a feature, spec, or price the
product doesn't have, and never invent a system/model name. If "Basis" is
cold_start, say plainly that this is a popular general pick since we don't
know their preferences yet. Output ONLY the sentence, no quotes, no preamble."""


def _why_openai(e: EligibleProduct, profile: PreferenceProfile, signals: dict, basis: str) -> str:
    from openai import OpenAI  # heavy import, kept local

    from app.config import OPENAI_API_KEY, OPENAI_MODEL

    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set")

    p = e.product
    price_fragment = f"€{p.price_monthly}/mo" if p.price_monthly else f"€{p.price_onetime} one-time"
    product_facts = (
        f"Product: {p.name} by {p.brand}. Type: {p.type.value}. "
        f"Features: {', '.join(p.features) or 'none listed'}. "
        f"Price: {price_fragment}."
    )
    profile_facts = (
        f"Customer profile - budget: {profile.budget_monthly_max or 'not specified'} EUR/mo, "
        f"features they mentioned: {', '.join(profile.features_mentioned) or 'none'}, "
        f"brands they've viewed: {', '.join(profile.brands_viewed) or 'none'}."
    )
    signal_facts = (
        f"Signals (0-1, higher is stronger): relevance={signals['relevance']}, "
        f"preference_fit={signals['preference']}, budget_fit={signals['budget']}, "
        f"popularity={signals['popularity']}. Basis: {basis}."
    )

    client = OpenAI(api_key=OPENAI_API_KEY)
    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": _WHY_SYSTEM_PROMPT},
            {"role": "user", "content": f"{product_facts}\n{profile_facts}\n{signal_facts}"},
        ],
        temperature=0.4,
        max_tokens=80,
        timeout=15,
    )
    text = (resp.choices[0].message.content or "").strip()
    if not text:
        raise RuntimeError("empty response from OpenAI")
    return text
