"""
Cart & checkout endpoints. Owned by P4.
Same session_id works from web (OneShop) and mobile view (OneApp) -> omnichannel.
"""
from fastapi import APIRouter
from pydantic import BaseModel

from app.contracts.models import Cart
from app.session.store import store

router = APIRouter(prefix="/cart", tags=["cart"])


class CartOp(BaseModel):
    session_id: str
    product_id: str
    qty: int = 1


class CheckoutReq(BaseModel):
    session_id: str


@router.get("", response_model=Cart)
def get_cart(session_id: str) -> Cart:
    return store.get(session_id).cart


@router.post("/add", response_model=Cart)
def add(op: CartOp) -> Cart:
    return store.add_to_cart(op.session_id, op.product_id, op.qty)


@router.post("/remove", response_model=Cart)
def remove(op: CartOp) -> Cart:
    return store.remove_from_cart(op.session_id, op.product_id)


@router.post("/checkout")
def checkout(req: CheckoutReq) -> dict:
    return store.checkout(req.session_id)
