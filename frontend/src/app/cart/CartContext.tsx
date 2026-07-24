import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import type { CartLineItem, Product } from "../types";

interface CartContextValue {
  items: CartLineItem[];
  count: number;
  subtotal: number;
  monthlyTotal: number;
  isInCart: (productId: number) => boolean;
  addItem: (product: Product, qty?: number) => void;
  removeItem: (productId: number) => void;
  updateQty: (productId: number, qty: number) => void;
  clearCart: () => void;
}

const CartContext = createContext<CartContextValue | null>(null);

export function CartProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<CartLineItem[]>([]);

  const addItem = (product: Product, qty = 1) => {
    setItems((prev) => {
      const existing = prev.find((i) => i.product.id === product.id);
      if (existing) {
        return prev.map((i) => i.product.id === product.id ? { ...i, qty: i.qty + qty } : i);
      }
      return [...prev, { product, qty }];
    });
  };

  const removeItem = (productId: number) => {
    setItems((prev) => prev.filter((i) => i.product.id !== productId));
  };

  const updateQty = (productId: number, qty: number) => {
    if (qty <= 0) {
      removeItem(productId);
      return;
    }
    setItems((prev) => prev.map((i) => i.product.id === productId ? { ...i, qty } : i));
  };

  const clearCart = () => setItems([]);

  const isInCart = (productId: number) => items.some((i) => i.product.id === productId);

  const count = useMemo(() => items.reduce((sum, i) => sum + i.qty, 0), [items]);
  const subtotal = useMemo(() => items.reduce((sum, i) => sum + i.product.price * i.qty, 0), [items]);
  const monthlyTotal = useMemo(() => items.reduce((sum, i) => sum + i.product.monthlyPrice * i.qty, 0), [items]);

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
