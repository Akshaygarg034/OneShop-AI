"""
Session store + cart. Owned by P4.
In-memory for the POC (deliberate debt - would be Redis at scale).

Holds, per session_id: conversation history, preference profile, cart.
The SAME session_id is used by both OneShop (web) and OneApp (mobile view)
-> that's how omnichannel continuity works.
"""
from app.contracts.models import Cart, CartItem, PreferenceProfile
from app.retrieval.catalog import get_product


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
        price = product.price_onetime if product else 0.0
        for item in session.cart.items:
            if item.product_id == product_id:
                item.qty += qty
                break
        else:
            session.cart.items.append(CartItem(product_id=product_id, qty=qty, price=price))
        self._recompute(session.cart)
        return session.cart

    def remove_from_cart(self, session_id: str, product_id: str) -> Cart:
        session = self.get(session_id)
        session.cart.items = [i for i in session.cart.items if i.product_id != product_id]
        self._recompute(session.cart)
        return session.cart

    def checkout(self, session_id: str) -> dict:
        session = self.get(session_id)
        summary = {
            "session_id": session_id,
            "items": [i.model_dump() for i in session.cart.items],
            "total": session.cart.subtotal,
            "status": "confirmed",
        }
        session.cart = Cart(session_id=session_id)  # clear after order
        return summary

    @staticmethod
    def _recompute(cart: Cart) -> None:
        cart.subtotal = round(sum(i.price * i.qty for i in cart.items), 2)


# Single shared instance for the whole app.
store = SessionStore()
