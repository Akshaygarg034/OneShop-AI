import { createContext, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type { CartLineItem, Product } from "../types";
import { getSessionId } from "../api/session";
import { getProducts } from "../api/mockApi";

// Cart state now lives on the backend, keyed by session_id (see
// backend/app/session/store.py) - that's what makes the cart survive a
// refresh and carry over across devices/channels sharing the same session_id.
// This context is just a thin, optimistic client cache over /cart/*.
// Keep this in sync with the catalog client: use the IPv4 backend explicitly.
const BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

interface BackendCartItem {
  product_id: string;
  qty: number;
  price: number;
  name: string;
  billing: "onetime" | "monthly";
}

interface BackendCartSummary {
  items: BackendCartItem[];
  onetime_total: number;
  monthly_total: number;
}

interface BackendCartResponse {
  items: BackendCartItem[];
  subtotal: number;
  monthly_total: number;
}

interface CartContextValue {
  items: CartLineItem[];
  count: number;
  subtotal: number;
  monthlyTotal: number;
  isInCart: (productId: string) => boolean;
  addItem: (product: Product, qty?: number) => void;
  removeItem: (productId: string) => void;
  updateQty: (productId: string, qty: number) => void;
  clearCart: () => void;
}

const CartContext = createContext<CartContextValue | null>(null);

// Used only for the brief gap before the catalog cache has loaded.
function placeholderProduct(item: BackendCartItem): Product {
  return {
    id: item.product_id, name: item.name, category: "", price: item.price,
    monthlyPrice: item.billing === "monthly" ? item.price : 0, image: "",
    badge: "", badgeColor: "", aiScore: 0, stars: 0, reviews: 0, tags: [],
    reasons: [], inStock: true, trend: "",
  };
}

function postCart(path: string, body: Record<string, unknown>): Promise<Response> {
  return fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: getSessionId(), ...body }),
  });
}

export function CartProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<CartLineItem[]>([]);
  const [subtotal, setSubtotal] = useState(0);
  const [monthlyTotal, setMonthlyTotal] = useState(0);
  const catalogRef = useRef<Map<string, Product>>(new Map());
  const refreshSeq = useRef(0);

  const applyCart = (data: BackendCartResponse | BackendCartSummary) => {
    setItems(data.items.map((i) => ({
      product: catalogRef.current.get(i.product_id) ?? placeholderProduct(i),
      qty: i.qty,
      billing: i.billing,
    })));
    setSubtotal("onetime_total" in data ? data.onetime_total : data.subtotal);
    setMonthlyTotal(data.monthly_total);
  };

  const refresh = async () => {
    const seq = ++refreshSeq.current;
    const res = await fetch(`${BASE}/cart/summary?session_id=${getSessionId()}`);
    if (!res.ok || seq !== refreshSeq.current) return;
    const data: BackendCartSummary = await res.json();
    if (seq !== refreshSeq.current) return;
    applyCart(data);
  };

  useEffect(() => {
    getProducts()
      .then((products) => products.forEach((p) => catalogRef.current.set(p.id, p)))
      .finally(refresh);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Re-fetch under the new identity when login/register swaps session_id from
  // the guest id to the user_id (the backend has already merged the guest
  // cart into the account by then).
  useEffect(() => {
    window.addEventListener("oneshop-session-changed", refresh);
    return () => window.removeEventListener("oneshop-session-changed", refresh);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const mutateCart = (path: string, body: Record<string, unknown>) =>
    postCart(path, body).then(async (res) => {
      if (!res.ok) return;
      // Apply the cart returned by the mutation directly — don't re-fetch
      // /cart/summary, which can briefly return stale data from Supabase and
      // make totals look unchanged after a bundle-suggestion add.
      const data: BackendCartResponse = await res.json();
      applyCart(data);
    });

  const addItem = (product: Product, qty = 1) => {
    catalogRef.current.set(product.id, product);
    mutateCart("/cart/add", { product_id: product.id, qty });
  };

  const removeItem = (productId: string) => {
    mutateCart("/cart/remove", { product_id: productId });
  };

  const updateQty = (productId: string, qty: number) => {
    mutateCart("/cart/set", { product_id: productId, qty });
  };

  const clearCart = () => {
    // Checkout already clears the cart server-side; this just resyncs local state.
    refresh();
  };

  const isInCart = (productId: string) => items.some((i) => i.product.id === productId);
  const count = useMemo(() => items.reduce((sum, i) => sum + i.qty, 0), [items]);

  return (
    <CartContext.Provider value={{ items, count, subtotal, monthlyTotal, isInCart, addItem, removeItem, updateQty, clearCart }}>
      {children}
    </CartContext.Provider>
  );
}

export function useCart() {
  const ctx = useContext(CartContext);
  if (!ctx) throw new Error("useCart must be used within a CartProvider");
  return ctx;
}
