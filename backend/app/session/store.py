"""
Session store + cart. Owned by P4.
In-memory for the POC (deliberate debt - would be Redis at scale).

Holds, per session_id: conversation history, preference profile, cart.
The SAME session_id is used by both OneShop (web) and OneApp (mobile view)
-> that's how omnichannel continuity works.
"""
from app.contracts.models import Cart, CartItem, PreferenceProfile, Product
from app.retrieval.catalog import get_product

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


class Session:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.history: list[dict] = []          # [{role, content}]
        self.profile = PreferenceProfile()
        self.cart = Cart(session_id=session_id)


class SessionStore:
    def __init__(self):
        self._sessions: dict[str, Session] = {}

    def get(self, session_id: str) -> Session:
        if session_id not in self._sessions:
            self._sessions[session_id] = Session(session_id)
        return self._sessions[session_id]

    # --- cart operations ---
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
        return session.cart

    def remove_from_cart(self, session_id: str, product_id: str) -> Cart:
        session = self.get(session_id)
        session.cart.items = [i for i in session.cart.items if i.product_id != product_id]
        self._recompute(session.cart)
        return session.cart

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
