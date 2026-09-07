"""API contract tests with the LLM mocked out. Asserts the exact shapes the
frontend parses, plus the preference/eligibility behavior end to end."""
import pytest

from app.agents.schemas import Understanding
from app.contracts.models import QueryFilters
from app.preferences.models import PreferenceDelta
from app.rate_limit import limiter

limiter.enabled = False

GUEST = "guest-test-session"


@pytest.fixture()
def fake_understanding(monkeypatch):
    """Queue Understanding results for successive /chat calls; skips the LLM."""
    queue: list[Understanding] = []

    async def fake(message, summary, recent, recall, prefs):
        return queue.pop(0)

    monkeypatch.setattr("app.agents.graph.understand", fake)
    return queue


@pytest.fixture(autouse=True)
def fake_compose(monkeypatch):
    async def fake(message, understanding, recommendations, products, prefs, stream=None):
        reply = f"Here are {len(recommendations)} picks."
        if stream:
            await stream(reply)
        return reply

    monkeypatch.setattr("app.agents.respond.compose_shopping_reply", fake)


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_catalog_contract(client):
    products = client.get("/catalog", params={"session_id": GUEST}).json()
    assert len(products) == 50
    sample = products[0]
    for field in ("id", "name", "brand", "price_onetime", "price_monthly", "in_stock",
                  "rating", "attributes", "confidence", "signals", "personalization_basis"):
        assert field in sample


def test_chat_budget_filtering(client, fake_understanding):
    fake_understanding.append(Understanding(
        intent="shopping",
        semantic_query="",
        filters=QueryFilters(product_types=["phone"], price_min=500, price_max=800, price_period="onetime"),
    ))
    resp = client.post("/chat", json={"session_id": GUEST, "message": "phone between 500 and 800"})
    assert resp.status_code == 200
    body = resp.json()
    for key in ("reply_text", "recommendations", "products", "nba", "cart", "receipts", "conversation_id"):
        assert key in body
    assert body["recommendations"], "expected recommendations in range"
    for product in body["products"]:
        assert 500 <= product["price_onetime"] <= 800
        assert product["type"] == "phone"

    history = client.get("/chat/history", params={
        "session_id": GUEST, "conversation_id": body["conversation_id"],
    }).json()
    assert [m["role"] for m in history["history"]] == ["user", "assistant"]
    assert history["history"][1]["recommendations"]

    conversations = client.get("/chat/conversations", params={"session_id": GUEST}).json()
    assert body["conversation_id"] in conversations["conversation_ids"]


def test_brand_exclusion_persists_across_turns(client, fake_understanding):
    session = "guest-exclusion-test"
    fake_understanding.append(Understanding(
        intent="preference_only",
        preference_deltas=[PreferenceDelta(target="brand", action="exclude", key="Apple")],
    ))
    first = client.post("/chat", json={"session_id": session, "message": "don't show me apple products"})
    assert first.status_code == 200

    fake_understanding.append(Understanding(
        intent="shopping", semantic_query="",
        filters=QueryFilters(product_types=["phone"]),
    ))
    second = client.post("/chat", json={"session_id": session, "message": "show me phones"}).json()
    assert second["products"], "expected non-apple recommendations"
    assert all(p["brand"].lower() != "apple" for p in second["products"])

    profile = client.get("/session/profile", params={"session_id": session}).json()
    assert profile["profile"]["brands"]["apple"]["hard"] is True


def test_cart_flow_and_behavioral_preferences(client):
    session = "guest-cart-test"
    catalog = client.get("/catalog").json()
    phone = next(p for p in catalog if p["type"] == "phone" and p["in_stock"])

    cart = client.post("/cart/add", json={"session_id": session, "product_id": phone["id"], "qty": 1}).json()
    assert {"items", "subtotal", "monthly_total"} <= cart.keys()
    assert cart["items"][0]["product_id"] == phone["id"]
    assert cart["subtotal"] == phone["price_onetime"]

    summary = client.get("/cart/summary", params={"session_id": session}).json()
    assert {"items", "onetime_total", "monthly_total", "shipping_note"} <= summary.keys()

    suggestions = client.get("/cart/suggestions", params={"session_id": session, "limit": 3}).json()
    assert len(suggestions) == 3
    assert all(s["id"] != phone["id"] for s in suggestions)

    # Behavioral signal: adding to cart should register brand affinity.
    profile = client.get("/session/profile", params={"session_id": session}).json()
    assert profile["profile"]["brands"][phone["brand"].lower()]["score"] > 0

    order = client.post("/cart/checkout", json={"session_id": session}).json()
    assert order["order_id"].startswith("TK-") and order["status"] == "confirmed"

    # Purchase inferred a budget prior for the purchased category (never a hard filter).
    profile = client.get("/session/profile", params={"session_id": session}).json()
    assert profile["profile"]["budgets"][phone["category"].lower()]["source"] == "inferred"

    cart_after = client.get("/cart/summary", params={"session_id": session}).json()
    assert cart_after["items"] == []


def test_auth_and_guest_merge(client):
    guest = "guest-merge-test"
    catalog = client.get("/catalog").json()
    accessory = next(p for p in catalog if p["type"] == "accessory" and p["in_stock"])
    client.post("/cart/add", json={"session_id": guest, "product_id": accessory["id"], "qty": 2})

    registered = client.post("/auth/register", json={
        "email": "shopper@example.com", "password": "s3curepass!", "name": "Shopper", "session_id": guest,
    })
    assert registered.status_code == 200
    body = registered.json()
    assert {"user_id", "email", "name", "token"} <= body.keys()
    user_id, token = body["user_id"], body["token"]

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert me["user_id"] == user_id

    merged = client.get("/cart/summary", params={"session_id": user_id},
                        headers={"Authorization": f"Bearer {token}"}).json()
    assert merged["items"][0]["product_id"] == accessory["id"]
    assert merged["items"][0]["qty"] == 2

    login = client.post("/auth/login", json={"email": "shopper@example.com", "password": "s3curepass!"})
    assert login.status_code == 200

    wrong = client.post("/auth/login", json={"email": "shopper@example.com", "password": "wrongpass1"})
    assert wrong.status_code == 401 and "detail" in wrong.json()


def test_user_sessions_require_token(client):
    registered = client.post("/auth/register", json={
        "email": "private@example.com", "password": "s3curepass!", "name": "P",
    }).json()
    user_id, token = registered["user_id"], registered["token"]

    assert client.post("/chat", json={"session_id": user_id, "message": "hi"}).status_code == 401
    assert client.get("/cart/summary", params={"session_id": user_id}).status_code == 401
    assert client.post("/cart/add", json={"session_id": user_id, "product_id": "x"}).status_code == 401
    assert client.get("/chat/history", params={"session_id": user_id}).status_code == 401

    authed = client.get("/cart/summary", params={"session_id": user_id},
                        headers={"Authorization": f"Bearer {token}"})
    assert authed.status_code == 200


def test_alternatives_exclude_previously_shown(client, fake_understanding):
    session = "guest-alternatives-test"
    filters = QueryFilters(product_types=["phone"], colors=["black"])

    fake_understanding.append(Understanding(intent="shopping", filters=filters))
    first = client.post("/chat", json={"session_id": session, "message": "black phones"}).json()
    shown = {p["id"] for p in first["products"]}
    assert shown

    fake_understanding.append(Understanding(intent="shopping", filters=filters, exclude_shown=True))
    second = client.post("/chat", json={
        "session_id": session, "message": "other than these, anything else?",
        "conversation_id": first["conversation_id"],
    }).json()
    alt = {p["id"] for p in second["products"]}
    assert alt, "expected alternative products"
    assert not (alt & shown), f"alternatives repeated already-shown products: {alt & shown}"
    assert "already_shown" in second["receipts"]["rules_fired"]

    # Keep asking for others until the matching set is exhausted — then the full
    # set is re-shown with an honest "you've seen everything" reply, never a dead end.
    seen = shown | alt
    for _ in range(10):
        fake_understanding.append(Understanding(intent="shopping", filters=filters, exclude_shown=True))
        resp = client.post("/chat", json={
            "session_id": session, "message": "any others?",
            "conversation_id": first["conversation_id"],
        }).json()
        ids = {p["id"] for p in resp["products"]}
        assert ids, "must never dead-end with zero products while matches exist"
        if ids & seen:
            assert "seen everything" in resp["reply_text"] or "only option" in resp["reply_text"]
            break
        seen |= ids
    else:
        raise AssertionError("exhaustion fallback never triggered")


def test_requested_count_shows_up_to_five(client, fake_understanding):
    fake_understanding.append(Understanding(
        intent="shopping",
        filters=QueryFilters(product_types=["phone"]),
        requested_count=5,
    ))
    resp = client.post("/chat", json={"session_id": GUEST, "message": "show me all phones"}).json()
    assert len(resp["products"]) == 5

    fake_understanding.append(Understanding(
        intent="shopping",
        filters=QueryFilters(product_types=["phone"]),
        requested_count=20,  # user asks for more than the cap
    ))
    resp = client.post("/chat", json={"session_id": GUEST, "message": "show me 20 phones"}).json()
    assert len(resp["products"]) == 5, "requested_count must be capped at max_recommendations"


def test_subcategory_filter_prevents_sibling_padding(client, fake_understanding):
    # "Suggest speakers" must return only speakers — never earbuds from the same category.
    fake_understanding.append(Understanding(
        intent="shopping",
        filters=QueryFilters(categories=["audio"], subcategories=["speaker"]),
    ))
    resp = client.post("/chat", json={"session_id": GUEST, "message": "suggest me speakers"}).json()
    assert resp["products"], "expected at least one speaker"
    assert all(p["subcategory"] == "speaker" for p in resp["products"])

    fake_understanding.append(Understanding(
        intent="shopping",
        filters=QueryFilters(subcategories=["smartwatch"]),
    ))
    resp = client.post("/chat", json={"session_id": GUEST, "message": "suggest a smartwatch"}).json()
    assert resp["products"], "expected smartwatches"
    assert all(p["subcategory"] == "smartwatch" for p in resp["products"])


def test_browse_all_ignores_saved_budget(client, fake_understanding):
    session = "guest-browse-all-test"
    fake_understanding.append(Understanding(
        intent="preference_only",
        preference_deltas=[PreferenceDelta(target="budget", action="set", number_min=200, number_max=400)],
    ))
    client.post("/chat", json={"session_id": session, "message": "my budget is 200 to 400"})

    # Recommendation ask — the saved budget applies.
    fake_understanding.append(Understanding(intent="shopping", filters=QueryFilters(product_types=["phone"])))
    rec = client.post("/chat", json={"session_id": session, "message": "suggest a phone"}).json()
    assert rec["products"]
    assert all(200 <= p["price_onetime"] <= 400 for p in rec["products"])

    # Exhaustive browse — the saved budget must NOT narrow the listing.
    fake_understanding.append(Understanding(
        intent="shopping", filters=QueryFilters(product_types=["phone"]), wants_all=True,
    ))
    browse = client.post("/chat", json={"session_id": session, "message": "show me all phones"}).json()
    assert len(browse["products"]) == 5
    assert any(p["price_onetime"] > 400 for p in browse["products"]), \
        "browse-all should include products outside the saved budget"


def test_login_required_for_chat_when_enabled(client, fake_understanding, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "require_login_for_chat", True)

    # Guests are blocked from chatting...
    resp = client.post("/chat", json={"session_id": "guest-gated", "message": "hi"})
    assert resp.status_code == 401 and "sign in" in resp.json()["detail"].lower()
    assert client.post("/chat/stream", json={"session_id": "guest-gated", "message": "hi"}).status_code == 401

    # ...but can still browse and use the cart.
    assert client.get("/catalog").status_code == 200
    assert client.get("/cart/summary", params={"session_id": "guest-gated"}).status_code == 200

    # A logged-in user chats normally.
    registered = client.post("/auth/register", json={
        "email": "gated@example.com", "password": "s3curepass!",
    }).json()
    fake_understanding.append(Understanding(intent="greeting"))
    resp = client.post(
        "/chat",
        json={"session_id": registered["user_id"], "message": "hi"},
        headers={"Authorization": f"Bearer {registered['token']}"},
    )
    assert resp.status_code == 200


def test_conversation_delete(client, fake_understanding):
    session = "guest-delete-test"
    fake_understanding.append(Understanding(intent="greeting"))
    conv = client.post("/chat", json={"session_id": session, "message": "hi"}).json()["conversation_id"]

    missing = client.delete(f"/chat/conversations/{conv}", params={"session_id": "guest-other"})
    assert missing.status_code == 404

    deleted = client.delete(f"/chat/conversations/{conv}", params={"session_id": session})
    assert deleted.status_code == 200
    remaining = client.get("/chat/conversations", params={"session_id": session}).json()
    assert conv not in remaining["conversation_ids"]


def test_chat_stream_events(client, fake_understanding):
    fake_understanding.append(Understanding(
        intent="shopping", semantic_query="",
        filters=QueryFilters(product_types=["audio"]),
    ))
    with client.stream("POST", "/chat/stream",
                       json={"session_id": GUEST, "message": "headphones"}) as resp:
        assert resp.status_code == 200
        payload = "".join(chunk for chunk in resp.iter_text())
    assert "event: token" in payload
    assert "event: recommendations" in payload
    assert "event: done" in payload


# --- Google Sign-In -------------------------------------------------------
# The ID-token verification itself is Google's JWT library; what's worth
# testing is our account resolution: create, link, and the no-password rule.

def _fake_google(monkeypatch, sub: str, email: str, name: str = ""):
    async def fake_verify(credential: str) -> dict:
        return {"sub": sub, "email": email, "name": name}

    monkeypatch.setattr("app.api.auth.verify_google_credential", fake_verify)


def test_google_signin_creates_account_and_merges_guest(client, monkeypatch):
    _fake_google(monkeypatch, "google-sub-1", "gshopper@example.com", "G Shopper")
    guest = "guest-google-test"
    catalog = client.get("/catalog").json()
    accessory = next(p for p in catalog if p["type"] == "accessory" and p["in_stock"])
    client.post("/cart/add", json={"session_id": guest, "product_id": accessory["id"], "qty": 1})

    res = client.post("/auth/google", json={"credential": "fake-id-token", "session_id": guest})
    assert res.status_code == 200
    body = res.json()
    assert body["email"] == "gshopper@example.com" and body["name"] == "G Shopper"

    # The guest cart followed the new account.
    cart = client.get("/cart/summary", params={"session_id": body["user_id"]},
                      headers={"Authorization": f"Bearer {body['token']}"}).json()
    assert cart["items"][0]["product_id"] == accessory["id"]

    # Signing in again returns the same account rather than a duplicate.
    again = client.post("/auth/google", json={"credential": "fake-id-token"})
    assert again.json()["user_id"] == body["user_id"]


def test_google_signin_links_to_existing_password_account(client, monkeypatch):
    registered = client.post("/auth/register", json={
        "email": "both@example.com", "password": "s3curepass!", "name": "Both",
    }).json()

    _fake_google(monkeypatch, "google-sub-2", "both@example.com", "Both")
    linked = client.post("/auth/google", json={"credential": "fake-id-token"})
    assert linked.status_code == 200
    # Same account, not a second one — and the password still works.
    assert linked.json()["user_id"] == registered["user_id"]
    assert client.post("/auth/login", json={
        "email": "both@example.com", "password": "s3curepass!",
    }).status_code == 200


def test_google_only_account_has_no_password_login(client, monkeypatch):
    _fake_google(monkeypatch, "google-sub-3", "googleonly@example.com")
    assert client.post("/auth/google", json={"credential": "fake-id-token"}).status_code == 200

    # An empty stored hash must never verify, whatever is submitted.
    for attempt in ("", " ", "anything"):
        res = client.post("/auth/login", json={"email": "googleonly@example.com", "password": attempt})
        assert res.status_code == 401, f"empty-hash account accepted password {attempt!r}"


def test_google_signin_rejected_when_unconfigured(client):
    """No GOOGLE_CLIENT_ID (the test default) means no credential can be trusted."""
    res = client.post("/auth/google", json={"credential": "any-token"})
    assert res.status_code == 401
    assert "not configured" in res.json()["detail"]
