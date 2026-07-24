// Cart + checkout. Owned by P4.
import React from "react";

export default function Cart({ cart, products, onRemove, onCheckout }) {
  const items = cart?.items || [];
  const nameOf = (id) => products[id]?.name || id;
  const remaining = (cart?.free_shipping_threshold || 0) - (cart?.subtotal || 0);

  return (
    <div className="panel">
      <h3>Cart</h3>
      {items.length === 0 && <div className="receipts">Your cart is empty.</div>}
      {items.map((it) => (
        <div key={it.product_id} className="cart-item">
          <span>{nameOf(it.product_id)} ×{it.qty}</span>
          <span>
            €{it.price * it.qty}{" "}
            <button className="btn secondary" onClick={() => onRemove(it.product_id)}>
              remove
            </button>
          </span>
        </div>
      ))}
      {items.length > 0 && (
        <>
          <div className="cart-total">Subtotal: €{cart.subtotal}</div>
          {remaining > 0 && remaining <= 20 && (
            <div className="nudge">Add €{remaining} more for free shipping!</div>
          )}
          <button className="btn" onClick={onCheckout}>Checkout</button>
        </>
      )}
    </div>
  );
}
