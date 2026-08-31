"""Cart/session persistence and checkout.

Supabase rows are versioned: every cart write is an optimistic-concurrency
compare-and-swap with retry, so two simultaneous mutations can't silently drop
one another. Checkout persists an order row before clearing the cart.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional

from app.config import get_settings
from app.contracts.models import Cart, CartItem, Product
from app.preferences.engine import merge as merge_preferences
from app.preferences.store import preference_store
from app.retrieval.catalog import get_product, load_catalog

logger = logging.getLogger(__name__)

_SESSIONS = "sessions"
_ORDERS = "orders"
_CAS_ATTEMPTS = 3

CartMutation = Callable[[Cart], Awaitable[None] | None]


def price_of(product: Optional[Product]) -> tuple[float, str]:
    """(unit_price, billing) for a catalog product. Plans/bundles are monthly
    commitments; devices and accessories are one-time purchases."""
    if product is None:
        return 0.0, "onetime"
    if product.is_monthly:
        return product.price_monthly, "monthly"
    return (product.price_onetime or product.price_monthly), "onetime"


def _recompute(cart: Cart) -> None:
    cart.subtotal = round(sum(i.price * i.qty for i in cart.items if i.billing == "onetime"), 2)
    cart.monthly_total = round(sum(i.price * i.qty for i in cart.items if i.billing == "monthly"), 2)


class MemorySessionBackend:
    def __init__(self) -> None:
        self._carts: dict[str, Cart] = {}
        self._orders: list[dict] = []
        self._lock = asyncio.Lock()

    async def get_cart(self, session_id: str) -> Cart:
        cart = self._carts.get(session_id)
        return cart.model_copy(deep=True) if cart else Cart(session_id=session_id)

    async def mutate_cart(self, session_id: str, mutation: CartMutation) -> Cart:
        async with self._lock:
            cart = self._carts.get(session_id) or Cart(session_id=session_id)
            result = mutation(cart)
            if asyncio.iscoroutine(result):
                await result
            _recompute(cart)
            self._carts[session_id] = cart
            return cart.model_copy(deep=True)

    async def record_order(self, order: dict) -> None:
        self._orders.append(order)


class SupabaseSessionBackend:
    async def _fetch(self, session_id: str) -> tuple[Cart, Optional[int]]:
        from app.clients import supabase_client

        resp = await (
            supabase_client().table(_SESSIONS)
            .select("cart,version").eq("session_id", session_id).limit(1).execute()
        )
        if resp.data:
            row = resp.data[0]
            cart_data = row.get("cart") or {}
            cart_data.setdefault("session_id", session_id)
            return Cart(**cart_data), row.get("version") or 1
        return Cart(session_id=session_id), None

    async def get_cart(self, session_id: str) -> Cart:
        cart, _ = await self._fetch(session_id)
        return cart

    async def mutate_cart(self, session_id: str, mutation: CartMutation) -> Cart:
        from app.clients import supabase_client

        client = supabase_client()
        for attempt in range(_CAS_ATTEMPTS):
            cart, version = await self._fetch(session_id)
            result = mutation(cart)
            if asyncio.iscoroutine(result):
                await result
            _recompute(cart)

            if version is None:
                try:
                    await client.table(_SESSIONS).insert({
                        "session_id": session_id, "cart": cart.model_dump(), "version": 1,
                    }).execute()
                    return cart
                except Exception:
                    logger.info("cart: insert race for %s, retrying", session_id)
                    continue

            resp = await (
                client.table(_SESSIONS)
                .update({"cart": cart.model_dump(), "version": version + 1})
                .eq("session_id", session_id).eq("version", version)
                .execute()
            )
            if resp.data:
                return cart
            logger.info("cart: version conflict for %s (attempt %d), retrying", session_id, attempt + 1)
        raise RuntimeError(f"cart update failed after {_CAS_ATTEMPTS} attempts for {session_id}")

    async def record_order(self, order: dict) -> None:
        from app.clients import supabase_client

        await supabase_client().table(_ORDERS).insert(order).execute()


class SessionStore:
    def __init__(self, backend=None) -> None:
        self._backend = backend or (
            SupabaseSessionBackend() if get_settings().uses_supabase else MemorySessionBackend()
        )

    async def get_cart(self, session_id: str) -> Cart:
        return await self._backend.get_cart(session_id)

    async def add_to_cart(self, session_id: str, product_id: str, qty: int = 1) -> Cart:
        product = await get_product(product_id)
        price, billing = price_of(product)

        def mutation(cart: Cart) -> None:
            for item in cart.items:
                if item.product_id == product_id:
                    item.qty += qty
                    return
            cart.items.append(CartItem(
                product_id=product_id, qty=qty, price=price,
                name=product.name if product else product_id, billing=billing,
            ))

        return await self._backend.mutate_cart(session_id, mutation)

    async def remove_from_cart(self, session_id: str, product_id: str) -> Cart:
        def mutation(cart: Cart) -> None:
            cart.items = [i for i in cart.items if i.product_id != product_id]

        return await self._backend.mutate_cart(session_id, mutation)

    async def set_cart_qty(self, session_id: str, product_id: str, qty: int) -> Cart:
        product = await get_product(product_id)
        price, billing = price_of(product)

        def mutation(cart: Cart) -> None:
            if qty <= 0:
                cart.items = [i for i in cart.items if i.product_id != product_id]
                return
            for item in cart.items:
                if item.product_id == product_id:
                    item.qty = qty
                    return
            cart.items.append(CartItem(
                product_id=product_id, qty=qty, price=price,
                name=product.name if product else product_id, billing=billing,
            ))

        return await self._backend.mutate_cart(session_id, mutation)

    async def suggest_additions(self, session_id: str, limit: int = 3) -> list[Product]:
        """Catalog-grounded 'complete your setup' suggestions: in-stock items that
        complement what's already in the cart."""
        cart = await self.get_cart(session_id)
        catalog = await load_catalog()
        in_cart = {i.product_id for i in cart.items}
        cart_products = [p for i in cart.items if (p := next((c for c in catalog if c.id == i.product_id), None))]
        cart_types = {p.type.value for p in cart_products}
        cart_brands = {p.brand.lower() for p in cart_products}
        device_types = {"phone", "tablet", "laptop", "wearable"}

        def score(p: Product) -> float:
            s = 0.0
            if p.type.value == "accessory":
                compatible = {str(c).lower() for c in p.attributes.get("compatible_with", [])}
                if compatible & in_cart:
                    s += 4
                if compatible & cart_brands:
                    s += 3
                if cart_types & device_types:
                    s += 2
            if p.type.value == "plan" and "phone" in cart_types and "plan" not in cart_types:
                s += 2
            return s + p.popularity

        candidates = [p for p in catalog if p.id not in in_cart and p.in_stock and p.stock > 0]
        candidates.sort(key=score, reverse=True)
        return candidates[:limit]

    async def cart_summary(self, session_id: str) -> dict:
        cart = await self.get_cart(session_id)
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

    async def checkout(self, session_id: str) -> dict:
        cart = await self.get_cart(session_id)
        order = {
            "order_id": f"TK-{uuid.uuid4().hex[:8].upper()}",
            "session_id": session_id,
            "items": [i.model_dump() for i in cart.items],
            "onetime_total": cart.subtotal,
            "monthly_total": cart.monthly_total,
            "free_shipping": cart.subtotal >= cart.free_shipping_threshold,
            "status": "confirmed",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await self._backend.record_order(order)

        def clear(c: Cart) -> None:
            c.items = []

        await self._backend.mutate_cart(session_id, clear)
        return {**order, "total": order["onetime_total"]}

    async def merge_guest_into_user(self, guest_session_id: str, user_id: str) -> None:
        """On login/register: fold the guest's cart, preferences, conversations,
        and memory vectors into the account identity."""
        if guest_session_id == user_id:
            return

        guest_cart = await self.get_cart(guest_session_id)
        if guest_cart.items:
            def mutation(cart: Cart) -> None:
                for item in guest_cart.items:
                    for existing in cart.items:
                        if existing.product_id == item.product_id:
                            existing.qty += item.qty
                            break
                    else:
                        cart.items.append(item)

            await self._backend.mutate_cart(user_id, mutation)

        prefs_store = preference_store()
        guest_prefs = await prefs_store.get(guest_session_id)
        user_prefs = await prefs_store.get(user_id)
        await prefs_store.save(user_id, merge_preferences(user_prefs, guest_prefs))
        await prefs_store.delete(guest_session_id)

        from app.conversations.memory import reassign_session as reassign_memory
        from app.conversations.store import conversation_store

        await conversation_store().reassign_session(guest_session_id, user_id)
        await reassign_memory(guest_session_id, user_id)


_store: Optional[SessionStore] = None


def session_store() -> SessionStore:
    global _store
    if _store is None:
        _store = SessionStore()
    return _store
