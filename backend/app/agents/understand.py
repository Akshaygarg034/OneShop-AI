"""The `understand` node: one structured LLM call that classifies intent,
extracts this turn's hard constraints, and emits durable preference deltas."""
from __future__ import annotations

import logging
import re

from tenacity import retry, stop_after_attempt, wait_exponential

from app.agents.schemas import Understanding
from app.clients import openai_client
from app.config import get_settings
from app.contracts.models import QueryFilters
from app.conversations.store import Message
from app.preferences.models import BudgetPreference, Preferences

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are the understanding module of a European electronics shopping assistant.
Analyze the user's latest message in the context of the conversation and output structured JSON.

CATALOG DOMAIN
- product types: phone, tablet, laptop, wearable, audio, accessory, plan, bundle
- categories: smartphones, tablets, laptops, wearables, audio, accessories, plans, bundles
- subcategories (the level shoppers ask at — ALWAYS set filters.subcategories when the user
  names one): smartphone, tablet, laptop, smartwatch, fitness_band, earbuds, headphones,
  neckband, speaker, case, charger, cable, powerbank, screen_protector, mount, hub,
  mobile_plan, home_internet, bundle.
  Map colloquial words: "speakers" -> speaker; "smartwatch"/"watch" -> smartwatch;
  "fitness tracker"/"band" -> fitness_band; "earbuds"/"buds"/"airpods-style" -> earbuds;
  "headphones"/"over-ear" -> headphones; "power bank" -> powerbank; "phone case" -> case.
  Someone asking for "speakers" must NOT get earbuds — the subcategory filter is what prevents it.
- attribute names you may reference in constraints: ram_gb, storage_gb, display_inch, display_type,
  refresh_rate_hz, battery_mah, main_camera_mp, front_camera_mp, chipset, os, sim, connectivity,
  weight_g, fast_charging_w, cpu, gpu, storage_type, battery_hours, battery_days, anc, form_factor,
  water_resistance, data_gb, speed_mbps, contract_months, accessory_type, stylus_support
- colors go in filters.colors (lowercase color names), never in attributes.

INTENT
- "shopping": the user wants products found, compared, or recommended.
- "greeting": a bare hello with no request.
- "off_topic": unrelated to shopping for these products (weather, jokes, coding, news...).
- "clarify": a shopping ask so vague you cannot search at all (e.g. just "I want to buy something").
  Prefer searching over clarifying whenever ANY constraint or category is present.
- "preference_only": the user states preferences/budget without asking to see products yet.
- "cart_question": asks about their cart, order, shipping, or checkout.

FILTERS (hard constraints for THIS turn only — the deterministic engine enforces them)
- Budget: "under 800" -> price_max=800. "between 500 and 800" -> price_min=500, price_max=800.
  price_period: "monthly" only for plan/tariff budgets or explicit per-month amounts; otherwise "onetime".
- CURRENCY: users may write Rs, ₹, INR, $, dollars, EUR, €, or a bare number. ALWAYS read the numeric
  amount as EUR (the shop's currency) and set stated_currency to the currency they used ("inr", "usd",
  "eur", or "" if none stated). "under Rs 600" means price_max=600.
- brands_include: brands explicitly requested. brands_exclude: brands to avoid THIS turn.
- attributes: numeric -> op "gte"/"lte"/"eq" with `number` ("at least 8GB RAM" -> ram_gb gte 8;
  "128GB storage" -> storage_gb eq 128); textual -> op "eq"/"in" with `values` (os in ["android"]).
- min_rating for "well-rated/highly rated" (use 4.3). on_sale_only for deals/discount asks.
- Resolve follow-ups from context: "and in black?" keeps the previous category/brand/budget and adds the color.
- BROWSE vs RECOMMEND: wants_all=true when the user asks to SEE ALL/every matching product
  ("show me all tablets", "list every yellow smartphone") — that is catalog browsing, and saved
  preferences must not narrow it (only constraints stated in the request itself apply).
  wants_all=false for recommendation asks ("suggest a tablet", "what's the best phone for me"),
  where saved preferences SHOULD shape results.
- REQUESTED COUNT: requested_count = the number of options the user explicitly asks for
  ("show me 2 options" -> 2). Leave 0 when they don't specify a number.
- ALTERNATIVES: when the user asks for options other than what was just shown ("other than this",
  "anything else?", "show me different ones", "what else do you have"), set exclude_shown=true and
  KEEP the constraints from the previous request (category, colors, budget...) — they still apply.
  The engine excludes the actual previously-shown products; you never list ids yourself.
- RELAXING CONSTRAINTS: when the assistant found nothing and offered to relax, and the user agrees
  ("yes", "show the closest options", "relax the budget", "ignore my budget"), intent is "shopping":
  re-run the previous search from context WITHOUT the constraint that failed (usually the price range —
  leave price_min/price_max null), keeping the rest (category, brand, attributes). If they had a stored
  budget and explicitly agreed to relax it, also emit {target: budget, action: retract}.

PREFERENCE DELTAS (durable — they shape ALL future turns; extract them even when intent is "shopping")
- Every delta MUST carry its subject in `key` (the brand/category/feature/attribute name, lowercase),
  e.g. {target: brand, action: exclude, key: "apple"}. A delta with an empty key is useless.
- Budgets are PER CATEGORY. "my budget for smartphones is 300 to 500" -> target=budget, action=set,
  key="smartphones", number_min=300, number_max=500. When the user states a budget while a category
  is being discussed, key = that category. Only a truly general budget ("I can spend up to 500
  overall") gets key="any". A budget delta requires the user OWNING the amount as theirs
  ("my budget", "I can spend", "I don't want to pay more than"). A price range attached to a
  search ("smartphones between 200 and 400") is ONLY a filter for that turn — never a budget delta.
  "ignore my budget" -> action=retract with key="any" (clears all); "forget my phone budget" ->
  action=retract, key="smartphones".
- "I love Samsung" -> target=brand, action=like. "not a fan of Xiaomi" -> action=dislike.
- "don't show me Apple products" / "never show Apple" -> target=brand, action=exclude
  (also add to filters.brands_exclude for this turn).
- "Apple is fine now" / "show me Apple again" -> target=brand, action=retract.
- "I need a great camera" -> target=feature, action=like, key=camera.
- "I prefer black phones" -> target=attribute, action=set, key=color, values=["black"].
- "I'm looking for deals" -> target=deals, action=set.
- Do NOT create deltas for one-off constraints ("show me something under 200 for my nephew").

SEMANTIC QUERY
- A short search phrase capturing what they want ("flagship phone great camera gaming"),
  WITHOUT constraints already in filters (no prices, no brand names that are filtered).
- Empty string when intent is not shopping.

Ask at most ONE clarification question, only when intent="clarify"."""

_CURRENCY_RE = re.compile(
    r"(?:€|\beur(?:os?)?\b|₹|\brs\.?\b|\binr\b|\brupees?\b|\$|\busd\b|\bdollars?\b)?\s*"
    r"(\d{2,6})(?:\s*(?:€|\beur(?:os?)?\b|₹|\brs\.?\b|\binr\b|\brupees?\b|\$|\busd\b|\bdollars?\b))?",
    re.IGNORECASE,
)
_BUDGET_HINT_RE = re.compile(r"under|below|max|budget|less than|between|up to|cheaper", re.IGNORECASE)


def _fallback_understanding(message: str) -> Understanding:
    """Degraded regex path used only when the LLM call fails after retries.
    Finds an obvious budget cap so filtering still works; everything else is a plain search."""
    filters = QueryFilters()
    if _BUDGET_HINT_RE.search(message):
        amounts = [float(m.group(1)) for m in _CURRENCY_RE.finditer(message) if m.group(1)]
        if len(amounts) >= 2:
            filters.price_min, filters.price_max = min(amounts), max(amounts)
        elif amounts:
            filters.price_max = amounts[0]
    return Understanding(intent="shopping", semantic_query=message, filters=filters)


def _context_block(summary: str, recent: list[Message], recall: list[str], prefs: Preferences) -> str:
    parts: list[str] = []
    for category, b in prefs.budgets.items():
        parts.append(
            f"Known budget for {category} ({b.source}): min={b.min}, max={b.max}, period={b.period}."
        )
    excluded = prefs.hard_excluded_brands()
    if excluded:
        parts.append("Brands the user excluded: " + ", ".join(sorted(excluded)) + ".")
    if summary:
        parts.append("Conversation summary:\n" + summary)
    if recall:
        parts.append("Relevant moments from past conversations:\n" + "\n".join(recall))
    if recent:
        parts.append("Recent messages:\n" + "\n".join(f"{m.role}: {m.content}" for m in recent))
    return "\n\n".join(parts) or "(no prior context)"


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=0.5, max=2), reraise=True)
async def _call_llm(message: str, context: str) -> Understanding:
    settings = get_settings()
    resp = await openai_client().chat.completions.parse(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"CONTEXT:\n{context}\n\nUSER MESSAGE:\n{message}"},
        ],
        response_format=Understanding,
        temperature=0.0,
        timeout=20,
    )
    parsed = resp.choices[0].message.parsed
    if parsed is None:
        raise RuntimeError("LLM returned no parsed understanding")
    return parsed


def _repair_deltas(result: Understanding) -> None:
    """The model sometimes leaves a delta's key empty while naming the brand in
    the filters. Backfill from the filters so durable exclusions never get lost."""
    exclude_pool = [b.lower() for b in result.filters.brands_exclude]
    include_pool = [b.lower() for b in result.filters.brands_include]
    for delta in result.preference_deltas:
        if delta.target == "brand" and not delta.key.strip():
            pool = exclude_pool if delta.action in ("exclude", "dislike") else include_pool
            if pool:
                delta.key = pool.pop(0)
    result.preference_deltas = [
        d for d in result.preference_deltas
        if d.key.strip() or d.target in ("budget", "deals")
    ]


async def understand(
    message: str,
    summary: str,
    recent: list[Message],
    recall: list[str],
    prefs: Preferences,
) -> Understanding:
    context = _context_block(summary, recent, recall, prefs)
    try:
        result = await _call_llm(message, context)
    except Exception:
        logger.exception("understand: LLM extraction failed; using regex fallback")
        return _fallback_understanding(message)

    _repair_deltas(result)

    # Belt-and-braces: a stated budget must persist even if the LLM only set filters.
    if (
        result.filters.price_max is not None
        and not any(d.target == "budget" for d in result.preference_deltas)
        and _mentions_persistent_budget(message)
    ):
        from app.engine.eligibility import filters_category
        from app.preferences.models import ANY_CATEGORY

        prefs.budgets[filters_category(result.filters) or ANY_CATEGORY] = BudgetPreference(
            min=result.filters.price_min,
            max=result.filters.price_max,
            period=result.filters.price_period or "onetime",
            source="stated",
        )
    return result


def _mentions_persistent_budget(message: str) -> bool:
    return "budget" in message.lower()
