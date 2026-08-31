"""Reply composition. One streaming LLM call for shopping replies; cheap
deterministic templates for everything that doesn't need generation."""
from __future__ import annotations

import logging
from typing import Awaitable, Callable, Optional

from app.agents.schemas import Understanding
from app.clients import openai_client
from app.config import get_settings
from app.contracts.models import Cart, EligibleProduct, Product, Recommendation
from app.preferences.models import Preferences

logger = logging.getLogger(__name__)

StreamHandler = Optional[Callable[[str], Awaitable[None]]]

GREETING_REPLY = (
    "Hey there, welcome! I'm your personal shopping assistant. I can help you find "
    "the right phone, laptop, tablet, audio gear, accessories, or plan — matched to "
    "your budget and what matters to you. What are you looking for today?"
)

OFF_TOPIC_REPLY = (
    "I'm here to help with shopping — phones, tablets, laptops, wearables, audio, "
    "accessories, plans, and bundles. I can't help with that question, but I'd be "
    "happy to help you find the right product."
)

_REPLY_SYSTEM_PROMPT = """You are a warm, sharp shopping assistant for a European electronics shop.
Write a short conversational reply (2-4 sentences) presenting the recommended products.

Rules:
- Ground EVERY claim strictly in the product facts provided. Never invent specs, prices, or discounts.
- Prices are in EUR (€). If the user wrote another currency (noted below), briefly mention that
  prices are in euros.
- Lead with the best pick and say concretely why it fits THIS user (their budget, brands, features).
- Don't list every spec — pick the 1-2 facts that matter for what they asked.
- No markdown headers, no bullet lists, no emoji. The products render as cards below your text,
  so don't repeat full spec sheets."""


def _product_facts(p: Product) -> str:
    unit = "/mo" if p.is_monthly else ""
    facts = [f"{p.name} ({p.brand}) — €{p.effective_price:g}{unit}"]
    if p.rating:
        facts.append(f"{p.rating}★ ({p.review_count:,} reviews)")
    if p.discount_pct > 0:
        facts.append(f"{p.discount_pct}% off (was €{p.original_price:g})")
    key_attrs = {k: v for k, v in p.attributes.items() if not isinstance(v, (dict, list))}
    if key_attrs:
        facts.append(", ".join(f"{k}={v}" for k, v in list(key_attrs.items())[:8]))
    if p.colors:
        facts.append("colors: " + ", ".join(p.colors))
    return " | ".join(facts)


async def compose_shopping_reply(
    message: str,
    understanding: Understanding,
    recommendations: list[Recommendation],
    products: dict[str, Product],
    prefs: Preferences,
    stream: StreamHandler = None,
) -> str:
    settings = get_settings()
    facts = "\n".join(
        f"{i + 1}. {_product_facts(products[r.product_id])}"
        for i, r in enumerate(recommendations) if r.product_id in products
    )
    profile_bits: list[str] = []
    for category, budget in prefs.budgets.items():
        if budget.max is None:
            continue
        unit = "/mo" if budget.period == "monthly" else ""
        low = f"€{budget.min:g}–" if budget.min is not None else "up to "
        profile_bits.append(f"{category} budget {low}€{budget.max:g}{unit} ({budget.source})")
    excluded = prefs.hard_excluded_brands()
    if excluded:
        profile_bits.append("excluded brands: " + ", ".join(sorted(excluded)))
    currency_note = (
        f"The user wrote amounts in {understanding.stated_currency.upper()}; they were read as EUR."
        if understanding.stated_currency and understanding.stated_currency != "eur" else ""
    )
    user_prompt = (
        f"User asked: {message}\n\n"
        f"User profile: {'; '.join(profile_bits) or 'nothing known yet'}\n"
        f"{currency_note}\n\n"
        f"Recommended products (already filtered and ranked — present these, in this order):\n{facts}"
    )

    try:
        response_stream = await openai_client().chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": _REPLY_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.5,
            max_tokens=300,
            timeout=30,
            stream=True,
        )
        chunks: list[str] = []
        async for chunk in response_stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                chunks.append(delta)
                if stream:
                    await stream(delta)
        reply = "".join(chunks).strip()
        if reply:
            return reply
        raise RuntimeError("empty streamed reply")
    except Exception:
        logger.exception("respond: reply generation failed; using template")
        reply = _template_shopping_reply(recommendations, products)
        if stream:
            await stream(reply)
        return reply


def _template_shopping_reply(recommendations: list[Recommendation], products: dict[str, Product]) -> str:
    if not recommendations:
        return "I found some options but couldn't rank them just now — mind trying again?"
    names = [products[r.product_id].name for r in recommendations if r.product_id in products]
    lead = "Here's my top pick" if len(names) == 1 else "Here are my top picks"
    return f"{lead}: {', '.join(names)}."


def all_seen_reply(count: int) -> str:
    """Everything matching was already shown — re-show the full set, honestly."""
    if count == 1:
        return (
            "That's actually the only option matching your criteria — here it is again. "
            "Want me to relax a constraint (color, budget, brand) to widen the search?"
        )
    return (
        f"You've actually seen everything that matches — there are {count} options in total, "
        "shown again below. Want me to relax a constraint (color, budget, brand) to find more?"
    )


def no_results_reply(understanding: Understanding, evaluated: list[EligibleProduct]) -> str:
    """Honest empty-result reply naming the constraint that filtered everything out."""
    failure_counts: dict[str, int] = {}
    for e in evaluated:
        for rule in e.failed_rules:
            failure_counts[rule] = failure_counts.get(rule, 0) + 1
    blocker = max(failure_counts, key=failure_counts.get) if failure_counts else ""
    hints = {
        "over_budget": "Everything matching is outside that price range — want me to relax the budget or show the closest options?",
        "out_of_stock": "Matching items are currently out of stock — want me to show alternatives?",
        "brand_excluded": "The matches are from brands you've excluded — say the word and I'll include them again.",
        "color_mismatch": "That color isn't available for these — want to see other colors?",
        "already_shown": "You've already seen everything that matches — want me to relax a constraint (budget, color, brand) to find more?",
    }
    default = "Want me to relax one of the constraints, or show the closest alternatives?"
    for prefix, hint in hints.items():
        if blocker.startswith(prefix):
            return f"I couldn't find anything in stock that fits all of that. {hint}"
    if blocker.startswith("attr_"):
        spec = blocker.removeprefix("attr_").removesuffix("_failed").replace("_", " ")
        return f"I couldn't find anything matching that {spec} requirement. {default}"
    return f"I couldn't find anything that fits all of that. {default}"


def preference_only_reply(prefs: Preferences, understanding: Understanding) -> str:
    """Acknowledge what was just learned, deterministically."""
    learned: list[str] = []
    for d in understanding.preference_deltas:
        if d.target == "budget" and d.number_max is not None:
            low = f"€{d.number_min:g}–" if d.number_min is not None else "up to "
            unit = "/mo" if d.period == "monthly" else ""
            scope = f"{d.key.replace('_', ' ')} " if d.key and d.key != "any" else ""
            learned.append(f"{scope}budget {low}€{d.number_max:g}{unit}")
        elif d.action == "exclude":
            learned.append(f"no {d.key.title()} products")
        elif d.action == "retract":
            learned.append(f"{d.key.title()} is back on the table")
        elif d.key:
            verb = {"like": "you like", "dislike": "you're not into", "set": "you prefer"}.get(d.action, "noted")
            learned.append(f"{verb} {d.key.replace('_', ' ')}")
    note = "; ".join(learned) if learned else "your preferences"
    currency = (
        " (I read your amounts as euros — all our prices are in €)"
        if understanding.stated_currency and understanding.stated_currency != "eur" else ""
    )
    return f"Got it — {note}{currency}. I'll keep that in mind. What would you like to see?"


def cart_question_reply(cart: Cart) -> str:
    if not cart.items:
        return "Your cart is empty right now. Want me to recommend something to get started?"
    lines = ", ".join(f"{i.qty}× {i.name}" for i in cart.items)
    parts = [f"You have {lines} in your cart."]
    if cart.subtotal > 0:
        parts.append(f"One-time total: €{cart.subtotal:g}.")
    if cart.monthly_total > 0:
        parts.append(f"Monthly commitment: €{cart.monthly_total:g}/mo.")
    remaining = cart.free_shipping_threshold - cart.subtotal
    if 0 < remaining <= 20:
        parts.append(f"You're €{remaining:g} away from free shipping.")
    return " ".join(parts)
