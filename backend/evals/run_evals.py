"""Behavioral eval harness for the chat agent.

Runs real LLM understanding against an isolated in-memory store, and checks the
behaviors that matter: budget ranges, currency normalization, persistent brand
exclusions, attribute/color filtering, behavioral cart signals, and scope guards.

Run:  cd backend && python -m evals.run_evals
Requires OPENAI_API_KEY in .env. Qdrant is optional (falls back to structured scan).
"""
from __future__ import annotations

import os

os.environ["STORAGE_BACKEND"] = "memory"

import asyncio
import uuid

from app.clients import close_clients, init_clients
from app.contracts.models import ChatResponse

PASSED, FAILED = 0, 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  PASS  {name}")
    else:
        FAILED += 1
        print(f"  FAIL  {name}  {detail}")


async def turn(session: str, message: str, conversation_id: str | None = None) -> ChatResponse:
    from app.agents.graph import run_turn

    return await run_turn(session, message, conversation_id or str(uuid.uuid4()))


async def eval_budget_range() -> None:
    print("\n[budget range]")
    session = f"guest-eval-{uuid.uuid4().hex[:8]}"
    resp = await turn(session, "I want a smartphone between 500 and 800 euros")
    check("returns recommendations", bool(resp.products), resp.reply_text[:120])
    check(
        "all prices within 500-800",
        all(500 <= p.price_onetime <= 800 for p in resp.products),
        str([(p.id, p.price_onetime) for p in resp.products]),
    )


async def eval_currency_normalization() -> None:
    print("\n[currency: Rs treated as EUR]")
    session = f"guest-eval-{uuid.uuid4().hex[:8]}"
    resp = await turn(session, "show me smartphones under Rs 400")
    check("returns recommendations", bool(resp.products), resp.reply_text[:120])
    check(
        "all prices under 400 EUR",
        all(p.price_onetime <= 400 for p in resp.products),
        str([(p.id, p.price_onetime) for p in resp.products]),
    )


async def eval_brand_exclusion_persists() -> None:
    print("\n[brand exclusion persists across turns]")
    session = f"guest-eval-{uuid.uuid4().hex[:8]}"
    conv = str(uuid.uuid4())
    await turn(session, "please never show me Apple products", conv)
    resp = await turn(session, "recommend me a good smartphone", conv)
    check("returns recommendations", bool(resp.products), resp.reply_text[:120])
    check(
        "no Apple products",
        all(p.brand.lower() != "apple" for p in resp.products),
        str([p.brand for p in resp.products]),
    )

    # New conversation — the exclusion must still hold.
    resp2 = await turn(session, "what phones do you have for me?", str(uuid.uuid4()))
    check(
        "exclusion holds in a NEW conversation",
        all(p.brand.lower() != "apple" for p in resp2.products),
        str([p.brand for p in resp2.products]),
    )

    # Retraction lifts it.
    conv3 = str(uuid.uuid4())
    await turn(session, "actually Apple is fine now, you can show them again", conv3)
    resp3 = await turn(session, "show me iPhones", conv3)
    check(
        "after retraction, Apple returns",
        any(p.brand.lower() == "apple" for p in resp3.products),
        str([p.brand for p in resp3.products]),
    )


async def eval_attribute_and_color_filters() -> None:
    print("\n[attribute + color filtering]")
    session = f"guest-eval-{uuid.uuid4().hex[:8]}"
    resp = await turn(session, "I need an android phone with at least 8GB RAM in black")
    check("returns recommendations", bool(resp.products), resp.reply_text[:120])
    check(
        "all have >= 8GB RAM",
        all(float(p.attributes.get("ram_gb", 0)) >= 8 for p in resp.products),
        str([(p.id, p.attributes.get("ram_gb")) for p in resp.products]),
    )
    check(
        "all available in black",
        all("black" in [c.lower() for c in p.colors] for p in resp.products),
        str([(p.id, p.colors) for p in resp.products]),
    )
    check(
        "all run android",
        all(str(p.attributes.get("os", "")).lower() == "android" for p in resp.products),
        str([(p.id, p.attributes.get("os")) for p in resp.products]),
    )


async def eval_combined_filters() -> None:
    print("\n[combined: brand + budget + attribute]")
    session = f"guest-eval-{uuid.uuid4().hex[:8]}"
    resp = await turn(session, "a Samsung phone under 700 euros with at least 128GB storage")
    check("returns recommendations", bool(resp.products), resp.reply_text[:120])
    check("all Samsung", all(p.brand.lower() == "samsung" for p in resp.products))
    check("all under 700", all(p.price_onetime <= 700 for p in resp.products))
    check(
        "all >= 128GB storage",
        all(float(p.attributes.get("storage_gb", 0)) >= 128 for p in resp.products),
        str([(p.id, p.attributes.get("storage_gb")) for p in resp.products]),
    )


async def eval_behavioral_signals() -> None:
    print("\n[cart behavior shapes preferences]")
    from app.preferences.store import preference_store
    from app.retrieval.catalog import load_catalog
    from app.preferences.engine import apply_event

    session = f"guest-eval-{uuid.uuid4().hex[:8]}"
    catalog = await load_catalog()
    sony = next(p for p in catalog if p.brand.lower() == "sony" and p.in_stock)

    store = preference_store()
    prefs = await store.get(session)
    prefs = apply_event(prefs, "cart_add", sony)
    prefs = apply_event(prefs, "purchase", sony)
    await store.save(session, prefs)

    check("brand affinity recorded", prefs.brands["sony"].score > 0.5)
    check(
        "inferred budget prior set for the purchased category",
        sony.category in prefs.budgets and prefs.budgets[sony.category].source == "inferred",
    )

    resp = await turn(session, "recommend me some audio gear")
    check("returns recommendations", bool(resp.products), resp.reply_text[:120])
    check("ranking is personalized", all(
        r.personalization_basis == "personalized" for r in resp.recommendations
    ))


async def eval_scope_and_clarification() -> None:
    print("\n[scope guard + greeting]")
    session = f"guest-eval-{uuid.uuid4().hex[:8]}"
    off_topic = await turn(session, "what's the weather in Berlin today?")
    check("off-topic refused without products", not off_topic.products)

    greeting = await turn(session, "hi")
    check("greeting gets a warm reply, no products", bool(greeting.reply_text) and not greeting.products)


async def main() -> int:
    await init_clients()
    try:
        await eval_budget_range()
        await eval_currency_normalization()
        await eval_brand_exclusion_persists()
        await eval_attribute_and_color_filters()
        await eval_combined_filters()
        await eval_behavioral_signals()
        await eval_scope_and_clarification()
    finally:
        await close_clients()

    print(f"\n{'=' * 40}\n{PASSED} passed, {FAILED} failed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
