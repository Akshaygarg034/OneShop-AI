"""Cart and checkout endpoints. Mutations are ownership-gated and feed
behavioral signals (add / remove / purchase) into the preference profile."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel

from app.auth.deps import assert_session_owner
from app.contracts.models import Cart, Product
from app.preferences.engine import BehaviorEvent, apply_event
from app.preferences.store import preference_store
from app.rate_limit import limiter
from app.retrieval.catalog import get_product
from app.session.store import session_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cart", tags=["cart"])


class CartOp(BaseModel):
    session_id: str
    product_id: str
    qty: int = 1


class CheckoutReq(BaseModel):
    session_id: str


async def _record_behavior(session_id: str, event: BehaviorEvent, product_id: str) -> None:
    """Behavioral preference learning must never fail a cart operation."""
    try:
        product = await get_product(product_id)
        if product is None:
            return
        store = preference_store()
        prefs = await store.get(session_id)
        await store.save(session_id, apply_event(prefs, event, product))
    except Exception:
        logger.exception("cart: failed to record %s signal for %s", event, session_id)


@router.get("/summary")
async def summary(session_id: str, authorization: str = Header(default="")) -> dict:
    assert_session_owner(session_id, authorization)
    return await session_store().cart_summary(session_id)


@router.post("/add", response_model=Cart)
@limiter.limit("60/minute")
async def add(op: CartOp, request: Request, authorization: str = Header(default="")) -> Cart:
    assert_session_owner(op.session_id, authorization)
    cart = await session_store().add_to_cart(op.session_id, op.product_id, op.qty)
    await _record_behavior(op.session_id, "cart_add", op.product_id)
    return cart


@router.post("/remove", response_model=Cart)
@limiter.limit("60/minute")
async def remove(op: CartOp, request: Request, authorization: str = Header(default="")) -> Cart:
    assert_session_owner(op.session_id, authorization)
    cart = await session_store().remove_from_cart(op.session_id, op.product_id)
    await _record_behavior(op.session_id, "cart_remove", op.product_id)
    return cart


@router.post("/set", response_model=Cart)
@limiter.limit("60/minute")
async def set_qty(op: CartOp, request: Request, authorization: str = Header(default="")) -> Cart:
    assert_session_owner(op.session_id, authorization)
    return await session_store().set_cart_qty(op.session_id, op.product_id, op.qty)


@router.get("/suggestions", response_model=list[Product])
async def suggestions(session_id: str, limit: int = 3, authorization: str = Header(default="")) -> list[Product]:
    assert_session_owner(session_id, authorization)
    return await session_store().suggest_additions(session_id, limit)


@router.post("/checkout")
@limiter.limit("10/minute")
async def checkout(req: CheckoutReq, request: Request, authorization: str = Header(default="")) -> dict:
    assert_session_owner(req.session_id, authorization)
    cart = await session_store().get_cart(req.session_id)
    order = await session_store().checkout(req.session_id)
    # A purchase is the strongest preference signal we have.
    for item in cart.items:
        await _record_behavior(req.session_id, "purchase", item.product_id)
    return order
