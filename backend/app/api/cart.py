"""
Cart & checkout endpoints. Owned by P4.
Same session_id works from web (OneShop) and mobile view (OneApp) -> omnichannel.
"""
from fastapi import APIRouter
from pydantic import BaseModel

from app.contracts.models import Cart, Product
from app.session.store import store

router = APIRouter(prefix="/cart", tags=["cart"])


class CartOp(BaseModel):
    session_id: str
    product_id: str
    qty: int = 1


class CartSetOp(BaseModel):
    session_id: str
    product_id: str
    qty: int


class CheckoutReq(BaseModel):
    session_id: str


@router.get("", response_model=Cart)
def get_cart(session_id: str) -> Cart:
    return store.get(session_id).cart


@router.get("/summary")
def summary(session_id: str) -> dict:
    """Display-ready cart for the checkout review screen (does NOT clear the cart)."""
    return store.cart_summary(session_id)


@router.post("/add", response_model=Cart)
def add(op: CartOp) -> Cart:
    return store.add_to_cart(op.session_id, op.product_id, op.qty)


@router.post("/remove", response_model=Cart)
def remove(op: CartOp) -> Cart:
    return store.remove_from_cart(op.session_id, op.product_id)


@router.post("/set", response_model=Cart)
def set_qty(op: CartSetOp) -> Cart:
    """Set an item's quantity directly (for a +/- stepper in the UI)."""
    return store.set_cart_qty(op.session_id, op.product_id, op.qty)


@router.get("/suggestions", response_model=list[Product])
def suggestions(session_id: str, limit: int = 3) -> list[Product]:
    """Catalog-grounded 'complete your setup' suggestions for the current cart."""
    return store.suggest_additions(session_id, limit)


@router.post("/checkout")
def checkout(req: CheckoutReq) -> dict:
    return store.checkout(req.session_id)
