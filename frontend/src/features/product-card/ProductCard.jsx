// Product card with grounded data + stock badge. Owned by P2.
// Shows only REAL catalog fields. The stock badge is the visible "trust" signal.
import React from "react";

export default function ProductCard({ product, why, onAdd }) {
  if (!product) return null;
  const price =
    product.price_monthly > 0
      ? `€${product.price_monthly}/mo`
      : `€${product.price_onetime}`;

  return (
    <div className="product-card">
      <div className="top">
        <div>
          <div className="name">{product.name}</div>
          <div className="brand">{product.brand}</div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div className="price">{price}</div>
          <span className={`badge ${product.in_stock ? "in" : "out"}`}>
            {product.in_stock ? "In stock" : "Out of stock"}
          </span>
        </div>
      </div>
      {why && <div className="why">💡 {why}</div>}
      <button
        className="btn"
        disabled={!product.in_stock}
        onClick={() => onAdd(product.id)}
      >
        Add to cart
      </button>
    </div>
  );
}
