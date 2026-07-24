"""
Ranking + "why this" + Next-Best-Action. Owned by P3.

EXPOSES:  recommend(eligible, profile, cart) -> (list[Recommendation], list[str] nba)

MOCK (now):  score by feature/brand match; template "why"; simple nudges.
REAL (P3):   keep the deterministic scoring, but generate the personalized `why`
             text with Grok. Import langchain_xai INSIDE the real branch.

GUARDRAIL (must always hold): every Recommendation.product_id MUST be in the
eligible set. The LLM can phrase the "why" but can NEVER introduce a product.
"""
from app.config import MOCK_MODE
from app.contracts.models import Cart, EligibleProduct, PreferenceProfile, Recommendation


def _score(e: EligibleProduct, profile: PreferenceProfile) -> float:
    p = e.product
    s = 0.0
    s += len(set(profile.features_mentioned).intersection(p.features)) * 2
    if p.brand in profile.brands_viewed:
        s += 2
    if p.brand in profile.rejected:
        s -= 5
    if profile.budget_monthly_max and p.price_monthly:
        # reward being comfortably under budget
        s += max(0, (profile.budget_monthly_max - p.price_monthly) / 10.0)
    return s


def _why_template(e: EligibleProduct, profile: PreferenceProfile) -> str:
    p = e.product
    bits = []
    matched = set(profile.features_mentioned).intersection(p.features)
    if "camera" in matched:
        bits.append("strong camera")
    if "eu_roaming" in matched:
        bits.append("EU roaming for travel")
    if "unlimited" in matched or "5g" in matched:
        bits.append("fast data")
    reason = ", ".join(bits) if bits else "a great all-round fit"
    budget_note = ""
    if profile.budget_monthly_max and p.price_monthly:
        budget_note = f" and it's within your €{int(profile.budget_monthly_max)}/mo budget"
    return f"{p.name} matches your need for {reason}{budget_note}."


def recommend(
    eligible: list[EligibleProduct],
    profile: PreferenceProfile,
    cart: Cart | None = None,
) -> tuple[list[Recommendation], list[str]]:
    ranked = sorted(eligible, key=lambda e: _score(e, profile), reverse=True)
    top = ranked[:3]

    if MOCK_MODE:
        why_fn = _why_template
    else:
        why_fn = _why_grok  # real Grok-generated explanations

    recs: list[Recommendation] = []
    for i, e in enumerate(top):
        recs.append(Recommendation(
            product_id=e.product.id,
            rank=i + 1,
            score=round(_score(e, profile), 2),
            why=why_fn(e, profile),
            bundle=_suggest_bundle(e),
        ))

    nba = _next_best_actions(top, cart)
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


def _why_grok(e: EligibleProduct, profile: PreferenceProfile) -> str:
    """
    TODO (P3): generate a short, personal "why this fits you" with Grok,
    grounded ONLY in this product's real fields + the profile. Never mention
    features the product doesn't have. Fall back to _why_template on error.
    """
    raise NotImplementedError("P3: implement Grok explanations, then set MOCK_MODE=false")
