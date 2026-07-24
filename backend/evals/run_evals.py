"""
Eval harness. Owned by P4.
This is your PROOF the system works - the answer to "how do you know it works?"

Run:  cd backend && python -m evals.run_evals

Each case asserts a GROUNDED behaviour and prints PASS/FAIL. Exit code is non-zero
if anything fails, so this doubles as a CI gate. Grouped by what it proves:
  TRUST         - never recommends junk (out-of-stock / over-budget / out-of-catalog)
  CONVERSATION  - clarifies when vague, populates receipts
  PERSONALIZATION - ranking adapts after the user rejects a brand
  CART          - cart math + free-shipping + checkout are correct
  AUTH          - register/login work and a guest cart survives login
  RAG           - semantic retrieval returns grounded catalog products (skipped if Qdrant is down)
"""
import os

# Force the harness fully offline/deterministic BEFORE app modules read config:
# mock generation (no OpenAI calls), JSON catalog, in-memory sessions, no live
# Supabase/Qdrant calls. Keeps evals fast, free, reproducible, and unable to
# pollute the real database. (The real OpenAI path is exercised in the demo.)
os.environ.setdefault("MOCK_MODE", "true")
os.environ.setdefault("CATALOG_BACKEND", "json")
os.environ.setdefault("SESSION_BACKEND", "memory")

import sys
import uuid

from app.agents.graph import run_pipeline
from app.auth.security import hash_password, verify_password
from app.auth.users_store import MemoryUserBackend, UserStore
from app.config import RAG_ENABLED
from app.retrieval.catalog import get_product, load_catalog
from app.session.store import Session, SessionStore


class SkipCase(Exception):
    """Raised by a case that can't run in this environment (e.g. Qdrant down)."""


def _run(message: str):
    """One-shot: fresh session, single message."""
    return run_pipeline(message, Session("eval"), uuid.uuid4().hex)


def _conversation():
    """Multi-turn: one persistent session + thread, returns a say() that advances it."""
    session = Session("eval-convo")
    conversation_id = uuid.uuid4().hex

    def say(message: str):
        return run_pipeline(message, session, conversation_id)

    return session, say


def _brand(product_id: str) -> str:
    p = get_product(product_id)
    return p.brand if p else ""


CASES = []


def case(group, name):
    def deco(fn):
        CASES.append((group, name, fn))
        return fn
    return deco


# --------------------------------------------------------------------------- #
# TRUST - never recommends junk                                                #
# --------------------------------------------------------------------------- #
@case("TRUST", "recommends something for a normal request")
def t_normal():
    r = _run("I need a phone under 40 euros with a good camera")
    assert r.recommendations, "expected at least one recommendation"


@case("TRUST", "never recommends an out-of-stock product")
def t_stock():
    r = _run("I want the iPhone 16 Pro")  # iphone16pro has stock 0 in seed data
    ids = [x.product_id for x in r.recommendations]
    assert "phone_iphone16pro" not in ids, "recommended an out-of-stock product!"


@case("TRUST", "never recommends over budget")
def t_budget():
    r = _run("show me a phone under 10 euros a month")
    for rec in r.recommendations:
        p = get_product(rec.product_id)
        if p and p.price_monthly > 0:
            assert p.price_monthly <= 10, f"{p.name} is over the 10 EUR budget"


@case("TRUST", "every recommendation is a real catalog product (no hallucination)")
def t_in_catalog():
    catalog_ids = {p.id for p in load_catalog()}
    r = _run("phone with a great camera for travel")
    for rec in r.recommendations:
        assert rec.product_id in catalog_ids, f"{rec.product_id} is not in the catalog!"


@case("TRUST", "every shown product is in stock AND within budget")
def t_all_grounded():
    r = _run("android phone under 20 euros with a camera")
    for rec in r.recommendations:
        p = get_product(rec.product_id)
        assert p and p.in_stock and p.stock > 0, f"{rec.product_id} is not in stock"
        if p.price_monthly > 0:
            assert p.price_monthly <= 20, f"{p.name} is over the 20 EUR budget"


@case("TRUST", "stays grounded when nothing fits (graceful, no invented product)")
def t_refuse():
    r = _run("get me the iPhone 16 Pro for 10 euros a month")
    assert "phone_iphone16pro" not in [x.product_id for x in r.recommendations], \
        "offered an out-of-stock / over-budget iPhone"
    assert r.reply_text.strip(), "expected a graceful reply even when refusing"


# --------------------------------------------------------------------------- #
# CONSTRAINTS - explicit asks become deterministic hard filters               #
# --------------------------------------------------------------------------- #
@case("CONSTRAINTS", "a brand request only returns that brand")
def t_brand_filter():
    r = _run("show me a Samsung phone")
    assert r.recommendations, "expected Samsung phones"
    for rec in r.recommendations:
        assert _brand(rec.product_id) == "Samsung", \
            f"{rec.product_id} is not Samsung but was shown for a Samsung request"


@case("CONSTRAINTS", "asking for an iPhone never swaps in another brand")
def t_iphone_no_swap():
    # iPhone 16 Pro is out of stock, iPhone 15 is over a tight budget -> nothing
    # eligible. The engine must REFUSE, not silently return a Samsung/Pixel.
    r = _run("I want an iPhone for 15 euros a month")
    brands = {_brand(x.product_id) for x in r.recommendations}
    assert brands <= {"Apple"}, f"an iPhone request returned non-Apple products: {brands}"


@case("CONSTRAINTS", "a plan request only returns plans")
def t_type_filter():
    r = _run("show me a plan with lots of data")
    assert r.recommendations, "expected at least one plan"
    for rec in r.recommendations:
        p = get_product(rec.product_id)
        assert p and p.type.value == "plan", \
            f"{rec.product_id} is a {p.type.value if p else '?'}, not a plan"


# --------------------------------------------------------------------------- #
# CONVERSATION                                                                 #
# --------------------------------------------------------------------------- #
@case("CONVERSATION", "asks for clarification when too vague")
def t_clarify():
    r = _run("something good")
    assert not r.recommendations and r.reply_text, "expected a clarification question"


@case("CONVERSATION", "politely declines an unrelated question")
def t_decline_unrelated():
    r = _run("What is the capital of France?")
    assert not r.recommendations, "unrelated questions must not return products"
    assert "can’t help with that question" in r.reply_text, "expected a polite scope refusal"


@case("CONVERSATION", "receipts are populated")
def t_receipts():
    r = _run("phone with a camera")
    assert r.receipts.retrieved_ids, "receipts should record what was retrieved"
    assert r.receipts.shown_ids == [x.product_id for x in r.recommendations], \
        "receipts.shown_ids must match what was actually shown"


@case("CONVERSATION", "assistant nudges are stored in history so follow-ups have a referent")
def t_nudge_in_history():
    # A phone recommendation emits an NBA nudge ("Add a protective case..."). That
    # nudge must be persisted into the conversation turn, otherwise a later "yes"
    # has nothing to refer to and the bot just repeats itself.
    session = Session("eval-nudge")
    r = run_pipeline("a phone with a good camera under 40 euros", session, "t")
    assert r.nba, "expected at least one nudge for a phone recommendation"
    turns = session.get_conversation("t")
    last_assistant = turns[-1]
    assert last_assistant["role"] == "assistant"
    assert r.nba[0] in last_assistant["content"], \
        "the nudge shown to the user was not saved into history"


# --------------------------------------------------------------------------- #
# PERSONALIZATION - ranking adapts to the profile                             #
# --------------------------------------------------------------------------- #
@case("PERSONALIZATION", "ranking changes after the user rejects a brand")
def t_personalize():
    session, say = _conversation()
    before = say("show me an android phone with a good camera under 40 euros")
    assert before.recommendations, "expected initial recommendations"

    say("actually I don't want Samsung")           # -> profile.rejected gets Samsung
    assert "Samsung" in session.profile.rejected, "rejection was not learned"

    after = say("show me a phone with a good camera")
    assert after.recommendations, "expected recommendations after the rejection"
    top_brand = _brand(after.recommendations[0].product_id)
    assert top_brand != "Samsung", f"top pick is still Samsung after rejecting it ({top_brand})"


@case("PERSONALIZATION", "profile learns brand affinity and persists on the session")
def t_profile_learns():
    session, say = _conversation()
    say("show me a Samsung phone")
    assert "Samsung" in session.profile.brands_viewed, "brand affinity was not learned"
    say("I take a lot of photos")
    assert "camera" in session.profile.features_mentioned, "feature interest was not learned"
    # The profile lives on the session, so it persists (Supabase) per user_id after login.
    assert session.profile is not None


# --------------------------------------------------------------------------- #
# CART - deterministic math + checkout                                        #
# --------------------------------------------------------------------------- #
@case("CART", "cart math splits one-time goods from the monthly commitment")
def t_cart_math():
    store = SessionStore()                          # isolated in-memory store
    store.add_to_cart("c", "phone_pixel8")          # monthly 15
    store.add_to_cart("c", "accessory_case")        # one-time 15
    store.add_to_cart("c", "accessory_charger")     # one-time 25
    cart = store.get("c").cart
    assert cart.subtotal == 40.0, f"one-time subtotal should be 40, got {cart.subtotal}"
    assert cart.monthly_total == 15.0, f"monthly total should be 15, got {cart.monthly_total}"


@case("CART", "free-shipping nudge computes the right gap")
def t_free_shipping():
    store = SessionStore()
    store.add_to_cart("c", "accessory_case")        # 15 -> 35 short of the 50 threshold
    s = store.cart_summary("c")
    assert s["free_shipping_qualified"] is False
    assert s["amount_to_free_shipping"] == 35.0, s["amount_to_free_shipping"]
    store.add_to_cart("c", "accessory_buds")        # +49 -> qualifies
    s = store.cart_summary("c")
    assert s["free_shipping_qualified"] is True, "should qualify for free shipping at 64 EUR"


@case("CART", "checkout confirms an order and clears the cart")
def t_checkout():
    store = SessionStore()
    store.add_to_cart("c", "accessory_buds")
    summary = store.checkout("c")
    assert summary["status"] == "confirmed", "checkout should confirm the order"
    assert summary["order_id"], "checkout should return an order id"
    assert store.cart_summary("c")["item_count"] == 0, "cart should be empty after checkout"


# --------------------------------------------------------------------------- #
# AUTH - accounts + guest-to-user continuity                                  #
# --------------------------------------------------------------------------- #
@case("AUTH", "password hashing round-trips and rejects wrong passwords")
def t_password_hash():
    hashed = hash_password("correct-horse-battery")
    assert verify_password("correct-horse-battery", hashed)
    assert not verify_password("wrong-password", hashed)


@case("AUTH", "duplicate email registration is rejected")
def t_duplicate_email():
    # Explicit in-memory backend so the test never touches the real Supabase users table.
    user_store = UserStore(MemoryUserBackend())
    user_store.create("dup@example.com", hash_password("pw1"))
    try:
        user_store.create("dup@example.com", hash_password("pw2"))
        assert False, "expected a duplicate email to raise"
    except ValueError:
        pass


@case("AUTH", "a guest's cart survives merging into their new user_id")
def t_merge_on_register():
    sessions = SessionStore()
    guest_id = f"guest-{uuid.uuid4().hex[:8]}"
    sessions.add_to_cart(guest_id, "phone_pixel8")
    sessions.add_to_cart(guest_id, "accessory_case")

    user_id = uuid.uuid4().hex
    merged = sessions.merge_guest_into_user(guest_id, user_id)

    assert merged.session_id == user_id
    assert len(merged.cart.items) == 2, "guest cart items should carry over"
    assert merged.cart.subtotal == 15.0 and merged.cart.monthly_total == 15.0


# --------------------------------------------------------------------------- #
# RAG - semantic retrieval (skipped if Qdrant/deps aren't available)          #
# --------------------------------------------------------------------------- #
@case("RAG", "semantic search returns grounded, in-catalog products")
def t_rag_grounded():
    try:
        from app.rag.retriever import search
    except ImportError:
        raise SkipCase("RAG deps not installed")
    try:
        hits = search("phone with a great camera for travel", k=3)
    except Exception as e:  # noqa - Qdrant down / collection not ingested
        raise SkipCase(f"Qdrant unavailable ({type(e).__name__})")
    if not hits:
        raise SkipCase("collection empty - run `python -m app.rag.ingestion`")

    catalog_ids = {p.id for p in load_catalog()}
    for h in hits:
        assert h["product_id"] in catalog_ids, \
            f"RAG returned {h['product_id']} which is not a real catalog product"


def main():
    passed = skipped = 0
    current_group = None
    for group, name, fn in CASES:
        if group != current_group:
            print(f"\n{group}")
            current_group = group
        try:
            fn()
            print(f"  PASS  {name}")
            passed += 1
        except SkipCase as e:
            print(f"  SKIP  {name}  ->  {e}")
            skipped += 1
        except AssertionError as e:
            print(f"  FAIL  {name}  ->  {e}")
        except Exception as e:  # noqa
            print(f"  ERROR {name}  ->  {type(e).__name__}: {e}")

    total = len(CASES)
    required = total - skipped
    print(f"\n{'=' * 52}")
    verdict = "ALL GREEN" if passed == required else "FAILURES"
    tail = f" ({skipped} skipped)" if skipped else ""
    print(f"  {passed}/{required} runnable eval cases passed{tail}   [{verdict}]")
    print(f"{'=' * 52}")
    return 0 if passed == required else 1


if __name__ == "__main__":
    sys.exit(main())
