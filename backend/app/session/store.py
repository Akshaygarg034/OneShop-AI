"""
Session store + cart. Owned by P4.

Holds, per session_id: conversation history, preference profile, cart.
The SAME session_id is used by both OneShop (web) and OneApp (mobile view)
-> that's how omnichannel continuity works.

Persistence is pluggable (P4's "state continuity is a distributed problem" story):
  - MemoryBackend   : in-memory dict. Zero config, the default. Dies on restart.
  - SupabaseBackend : rows in Supabase Postgres. Survives restart AND lets a stateless
                      service scale horizontally (the real omnichannel answer).

Selection is driven by config (SESSION_BACKEND / SUPABASE_URL+KEY). If Supabase is
requested but unreachable we log and fall back to memory, so the demo can never break.

Heavy imports (the supabase client) live INSIDE the backend so mock mode needs nothing
installed.
"""
from __future__ import annotations

import logging

from app.config import SESSION_BACKEND, SUPABASE_KEY, SUPABASE_URL
from app.contracts.models import Cart, CartItem, PreferenceProfile, Product
from app.retrieval.catalog import get_product, load_catalog
from app.supabase_diag import describe_supabase_error

logger = logging.getLogger(__name__)

# Product types billed monthly (device-on-plan / tariffs) vs one-time (accessories).
_MONTHLY_TYPES = {"phone", "plan"}


def _price_of(product: Product | None) -> tuple[float, str]:
    """Return (unit_price, billing) for a catalog product.

    Phones/plans are device-on-plan -> priced monthly. Accessories/bundles are
    one-time. This fixes the old bug where phones (price_onetime == 0) added to the
    cart for EUR 0 and the subtotal never moved.
    """
    if product is None:
        return 0.0, "onetime"
    if product.type.value in _MONTHLY_TYPES:
        return product.price_monthly, "monthly"
    # one-time good: prefer the upfront price, fall back to monthly if that's all we have
    return (product.price_onetime or product.price_monthly), "onetime"


def _merge_profiles(target: PreferenceProfile, guest: PreferenceProfile) -> PreferenceProfile:
    """Union list fields, prefer the target's budget unless it's unset."""
    return PreferenceProfile(
        budget_monthly_max=target.budget_monthly_max if target.budget_monthly_max is not None
        else guest.budget_monthly_max,
        brands_viewed=list(dict.fromkeys(target.brands_viewed + guest.brands_viewed)),
        features_mentioned=list(dict.fromkeys(target.features_mentioned + guest.features_mentioned)),
        categories_browsed=list(dict.fromkeys(target.categories_browsed + guest.categories_browsed)),
        rejected=list(dict.fromkeys(target.rejected + guest.rejected)),
    )


class Session:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.history: list[dict] = []          # [{role, content}]
        self.profile = PreferenceProfile()
        self.cart = Cart(session_id=session_id)

    # --- serialization (for persistent backends) ---
    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "history": self.history,
            "profile": self.profile.model_dump(),
            "cart": self.cart.model_dump(),
        }

    @classmethod
    def from_dict(cls, session_id: str, data: dict) -> "Session":
        s = cls(session_id)
        s.history = data.get("history") or []
        s.profile = PreferenceProfile(**(data.get("profile") or {}))
        cart_data = data.get("cart") or {"session_id": session_id}
        cart_data.setdefault("session_id", session_id)
        s.cart = Cart(**cart_data)
        return s


# --------------------------------------------------------------------------- #
# Backends                                                                     #
# --------------------------------------------------------------------------- #
class MemoryBackend:
    """In-memory sessions. Fast, zero config, wiped on restart (deliberate POC debt)."""
    name = "memory"

    def __init__(self):
        self._sessions: dict[str, Session] = {}

    def get_session(self, session_id: str) -> Session:
        if session_id not in self._sessions:
            self._sessions[session_id] = Session(session_id)
        return self._sessions[session_id]

    def save(self, session: Session) -> None:
        # session is the live object already held in the dict -> nothing to do.
        self._sessions[session.session_id] = session


class SupabaseBackend:
    """Sessions persisted as rows in Supabase Postgres.

    Table (see supabase_schema.sql): sessions(session_id pk, history jsonb,
    profile jsonb, cart jsonb, updated_at). Upsert on the primary key -> writes are
    idempotent, so a retried cart-add can't double-charge. The service is stateless:
    every request loads fresh from Postgres and saves back, which is exactly what lets
    web + mobile share one session and lets the service scale horizontally.
    """
    name = "supabase"

    def __init__(self, url: str, key: str, table: str = "sessions"):
        from supabase import create_client  # heavy import, kept local
        self._client = create_client(url, key)
        self._table = table
        self._url = url
        # Fail fast so _make_backend can fall back to memory if creds/table are wrong.
        self._client.table(self._table).select("session_id").limit(1).execute()

    def get_session(self, session_id: str) -> Session:
        try:
            resp = (
                self._client.table(self._table)
                .select("*")
                .eq("session_id", session_id)
                .limit(1)
                .execute()
            )
            if resp.data:
                return Session.from_dict(session_id, resp.data[0])
        except Exception as e:  # noqa - never let a read blip break a turn
            logger.error(
                "session: Supabase read failed for %s - %s",
                session_id, describe_supabase_error(e, self._url),
            )
        return Session(session_id)

    def save(self, session: Session) -> None:
        try:
            self._client.table(self._table).upsert(
                session.to_dict(), on_conflict="session_id"
            ).execute()
        except Exception as e:  # noqa - a write blip must not crash the demo
            logger.error(
                "session: Supabase write failed for %s - %s",
                session.session_id, describe_supabase_error(e, self._url),
            )


def _make_backend():
    want = (SESSION_BACKEND or "auto").strip().lower()
    use_supabase = want == "supabase" or (want == "auto" and SUPABASE_URL and SUPABASE_KEY)
    if use_supabase:
        if not (SUPABASE_URL and SUPABASE_KEY):
            logger.warning("SESSION_BACKEND=supabase but SUPABASE_URL/KEY missing; using in-memory sessions.")
            return MemoryBackend()
        try:
            backend = SupabaseBackend(SUPABASE_URL, SUPABASE_KEY)
            logger.info("session: using Supabase persistence.")
            return backend
        except Exception as e:  # noqa - keep the demo bulletproof
            logger.error(
                "session: Supabase unavailable, falling back to in-memory (sessions won't "
                "survive a restart) - %s",
                describe_supabase_error(e, SUPABASE_URL),
            )
            return MemoryBackend()
    return MemoryBackend()


# --------------------------------------------------------------------------- #
# Store facade (unchanged public API: get / add_to_cart / remove / checkout)   #
# --------------------------------------------------------------------------- #
class SessionStore:
    def __init__(self, backend=None):
        self._backend = backend or _make_backend()

    @property
    def backend_name(self) -> str:
        return getattr(self._backend, "name", "memory")

    def get(self, session_id: str) -> Session:
        return self._backend.get_session(session_id)

    def save(self, session: Session) -> None:
        """Persist a session after the pipeline mutates its history/profile/cart.
        No-op for the memory backend; a Postgres upsert for Supabase."""
        self._backend.save(session)

    # --- cart operations (mutate, then persist) ---
    def add_to_cart(self, session_id: str, product_id: str, qty: int = 1) -> Cart:
        session = self.get(session_id)
        product = get_product(product_id)
        price, billing = _price_of(product)
        for item in session.cart.items:
            if item.product_id == product_id:
                item.qty += qty
                break
        else:
            session.cart.items.append(CartItem(
                product_id=product_id,
                qty=qty,
                price=price,
                name=product.name if product else product_id,
                billing=billing,
            ))
        self._recompute(session.cart)
        self.save(session)
        return session.cart

    def remove_from_cart(self, session_id: str, product_id: str) -> Cart:
        session = self.get(session_id)
        session.cart.items = [i for i in session.cart.items if i.product_id != product_id]
        self._recompute(session.cart)
        self.save(session)
        return session.cart

    def set_cart_qty(self, session_id: str, product_id: str, qty: int) -> Cart:
        """Set an item's quantity directly (for a +/- stepper). qty <= 0 removes it."""
        session = self.get(session_id)
        if qty <= 0:
            session.cart.items = [i for i in session.cart.items if i.product_id != product_id]
        else:
            for item in session.cart.items:
                if item.product_id == product_id:
                    item.qty = qty
                    break
            else:
                product = get_product(product_id)
                price, billing = _price_of(product)
                session.cart.items.append(CartItem(
                    product_id=product_id, qty=qty, price=price,
                    name=product.name if product else product_id, billing=billing,
                ))
        self._recompute(session.cart)
        self.save(session)
        return session.cart

    def suggest_additions(self, session_id: str, limit: int = 3) -> list[Product]:
        """Catalog-grounded 'complete your setup' suggestions: in-stock items not
        already in the cart, weighted toward categories that complement what's
        already there (a phone in cart -> prioritize accessories/plans). No
        fabricated scores or social proof - just a deterministic filter + sort
        over real catalog data."""
        cart = self.get(session_id).cart
        in_cart_ids = {i.product_id for i in cart.items}
        cart_types = {p.type.value for i in cart.items if (p := get_product(i.product_id))}

        def _score(p: Product) -> int:
            s = 0
            if "phone" in cart_types and p.type.value == "accessory":
                s += 3
            if "phone" in cart_types and p.type.value == "plan":
                s += 2
            return s

        candidates = [p for p in load_catalog() if p.id not in in_cart_ids and p.in_stock and p.stock > 0]
        return sorted(candidates, key=_score, reverse=True)[:limit]

    def cart_summary(self, session_id: str) -> dict:
        """Read-only, display-ready cart summary for the checkout review screen.
        Does NOT clear the cart (unlike checkout). Splits today's goods from the
        monthly commitment and computes the free-shipping nudge."""
        cart = self.get(session_id).cart
        remaining = round(max(0.0, cart.free_shipping_threshold - cart.subtotal), 2)
        qualifies = cart.subtotal >= cart.free_shipping_threshold
        return {
            "session_id": session_id,
            "items": [i.model_dump() for i in cart.items],
            "item_count": sum(i.qty for i in cart.items),
            "onetime_total": cart.subtotal,
            "monthly_total": cart.monthly_total,
            "free_shipping_threshold": cart.free_shipping_threshold,
            "free_shipping_qualified": qualifies,
            "amount_to_free_shipping": 0.0 if qualifies else remaining,
            "shipping_note": (
                "You've unlocked free shipping." if qualifies
                else f"Add €{remaining:g} more for free shipping." if remaining > 0
                else "Add an accessory to qualify for free shipping."
            ),
        }

    def merge_guest_into_user(self, guest_session_id: str, user_id: str) -> Session:
        """Called on register/login: fold a guest's history/profile/cart into the
        session keyed by their permanent user_id, so nothing from the anonymous
        browsing session is lost once they have an account. From then on the
        frontend uses user_id as its session_id - the same store, no new concept.
        """
        if guest_session_id == user_id:
            return self.get(user_id)

        guest = self.get(guest_session_id)
        target = self.get(user_id)

        target.history = target.history + guest.history
        target.profile = _merge_profiles(target.profile, guest.profile)

        for item in guest.cart.items:
            for existing in target.cart.items:
                if existing.product_id == item.product_id:
                    existing.qty += item.qty
                    break
            else:
                target.cart.items.append(item)
        self._recompute(target.cart)

        self.save(target)
        return target

    def checkout(self, session_id: str) -> dict:
        session = self.get(session_id)
        cart = session.cart
        free_shipping = cart.subtotal >= cart.free_shipping_threshold
        summary = {
            "session_id": session_id,
            "order_id": f"TK-{abs(hash((session_id, len(cart.items), cart.subtotal))) % 1_000_000:06d}",
            "items": [i.model_dump() for i in cart.items],
            "onetime_total": cart.subtotal,          # goods paid today
            "monthly_total": cart.monthly_total,     # recurring commitment
            "total": cart.subtotal,                  # back-compat: today's charge
            "free_shipping": free_shipping,
            "status": "confirmed",
        }
        session.cart = Cart(session_id=session_id)  # clear after order
        self.save(session)
        return summary

    @staticmethod
    def _recompute(cart: Cart) -> None:
        cart.subtotal = round(
            sum(i.price * i.qty for i in cart.items if i.billing == "onetime"), 2
        )
        cart.monthly_total = round(
            sum(i.price * i.qty for i in cart.items if i.billing == "monthly"), 2
        )


# Single shared instance for the whole app.
store = SessionStore()
