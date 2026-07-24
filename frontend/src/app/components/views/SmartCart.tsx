import { useEffect, useMemo, useState, type CSSProperties } from "react";
import {
  ShoppingCart, Trash2, Sparkles, Tag, ChevronRight, ChevronLeft,
  Check, Package, Shield, Truck, Minus, Plus, CheckCircle2, AlertTriangle,
} from "lucide-react";
import { useCart } from "../../cart/CartContext";
import { useAuth } from "../../auth/AuthContext";
import { getBundleSuggestions, getLiveActivity, createOrder } from "../../api/mockApi";
import type { OrderResult } from "../../api/mockApi";
import { formatEUR } from "../../lib/format";
import { AuthModal } from "../AuthModal";
import type { Product, ShippingDetails, PaymentDetails } from "../../types";

const steps = ["Cart", "Details", "Payment", "Confirm"];
// A real inventory signal: only worth surfacing once stock is genuinely low.
const LOW_STOCK_THRESHOLD = 10;

interface SmartCartProps {
  onContinueShopping: () => void;
}

export function SmartCart({ onContinueShopping }: SmartCartProps) {
  const { items, subtotal, monthlyTotal, updateQty, removeItem, addItem, isInCart, clearCart } = useCart();
  const { user } = useAuth();
  const [step, setStep] = useState(0);
  const [authOpen, setAuthOpen] = useState(false);
  const [bundles, setBundles] = useState<Product[]>([]);
  const [bundlesLoading, setBundlesLoading] = useState(true);
  const [liveActivity, setLiveActivity] = useState<{ viewers: number; stockLeft: number } | null>(null);

  const [shipping, setShipping] = useState<ShippingDetails>({ fullName: "", address: "", city: "", postalCode: "" });
  const [payment, setPayment] = useState<PaymentDetails>({ cardName: "", cardNumber: "", expiry: "", cvc: "" });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [placingOrder, setPlacingOrder] = useState(false);
  const [orderResult, setOrderResult] = useState<OrderResult | null>(null);

  const cartIds = useMemo(() => items.map((i) => i.product.id).sort().join(","), [items]);
  const firstItem = items[0]?.product;

  useEffect(() => {
    setBundlesLoading(true);
    getBundleSuggestions(items.map((i) => i.product.id)).then((res) => {
      setBundles(res);
      setBundlesLoading(false);
    });
  }, [cartIds]);

  useEffect(() => {
    if (!firstItem) {
      setLiveActivity(null);
      return;
    }
    getLiveActivity(firstItem.id).then(setLiveActivity);
  }, [firstItem?.id]);

  const bundleDiscountRate = items.length >= 2 ? 0.05 : 0;
  // Discount only applies to one-time goods (accessories, upfront device cost)
  const bundleDiscount = subtotal * bundleDiscountRate;
  const onetimeTotal = subtotal - bundleDiscount;
  const total = onetimeTotal; // kept for legacy confirm-step usage
  const onetimeItemCount = useMemo(
    () => items.filter((i) => i.billing === "onetime").reduce((sum, i) => sum + i.qty, 0),
    [items],
  );

  const validateShipping = () => {
    const e: Record<string, string> = {};
    if (!shipping.fullName.trim()) e.fullName = "Required";
    if (!shipping.address.trim()) e.address = "Required";
    if (!shipping.city.trim()) e.city = "Required";
    if (!shipping.postalCode.trim()) e.postalCode = "Required";
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const validatePayment = () => {
    const e: Record<string, string> = {};
    const digits = payment.cardNumber.replace(/\s/g, "");
    if (!payment.cardName.trim()) e.cardName = "Required";
    if (!/^\d{16}$/.test(digits)) e.cardNumber = "Enter a 16-digit card number";
    if (!/^(0[1-9]|1[0-2])\/\d{2}$/.test(payment.expiry)) e.expiry = "Use MM/YY";
    if (!/^\d{3,4}$/.test(payment.cvc)) e.cvc = "3-4 digits";
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleContinue = () => {
    if (step === 0) {
      if (items.length === 0) return;
      // Guests can add to cart; checkout requires an account.
      if (!user) { setAuthOpen(true); return; }
      setStep(1);
    } else if (step === 1) {
      if (validateShipping()) setStep(2);
    } else if (step === 2) {
      if (validatePayment()) setStep(3);
    } else if (step === 3) {
      setPlacingOrder(true);
      createOrder(shipping, payment, items)
        .then((result) => {
          setOrderResult(result);
          clearCart();
        })
        .finally(() => setPlacingOrder(false));
    }
  };

  const inputStyle: CSSProperties = {
    width: "100%",
    background: "var(--input-background)",
    border: "1.5px solid rgba(var(--primary-rgb),0.25)",
    borderRadius: 12,
    padding: "10px 14px",
    fontSize: 13,
    color: "var(--foreground)",
    outline: "none",
  };
  const labelStyle: CSSProperties = { fontSize: 11, color: "var(--muted-foreground)", marginBottom: 5, display: "block" };
  const errorStyle: CSSProperties = { fontSize: 10, color: "#FF3B30", marginTop: 3 };

  // ---- Order success ----
  if (orderResult) {
    return (
      <div className="p-6" style={{ maxWidth: 560, margin: "80px auto", textAlign: "center", color: "var(--foreground)" }}>
        <div
          style={{
            width: 64, height: 64, borderRadius: "50%", background: "rgba(34,197,94,0.12)",
            display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 20px",
          }}
        >
          <CheckCircle2 size={32} style={{ color: "#22C55E" }} />
        </div>
        <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 8 }}>Order placed!</h1>
        <p style={{ fontSize: 13, color: "var(--muted-foreground-2)", marginBottom: 24 }}>
          Confirmation and tracking details have been sent to your email.
        </p>
        <div
          style={{
            background: "var(--card)", border: "1px solid rgba(var(--border-rgb),0.07)", borderRadius: 20,
            padding: 20, marginBottom: 24, display: "flex", justifyContent: "space-around",
          }}
        >
          <div>
            <p style={{ fontSize: 10, color: "var(--muted-foreground)", marginBottom: 4 }}>ORDER NUMBER</p>
            <p style={{ fontSize: 15, fontWeight: 700 }}>{orderResult.orderNumber}</p>
          </div>
          <div>
            <p style={{ fontSize: 10, color: "var(--muted-foreground)", marginBottom: 4 }}>ESTIMATED DELIVERY</p>
            <p style={{ fontSize: 15, fontWeight: 700 }}>{orderResult.estimatedDelivery}</p>
          </div>
        </div>
        <button
          onClick={onContinueShopping}
          style={{ padding: "12px 26px", background: "var(--primary)", border: "none", borderRadius: 50, color: "#fff", fontSize: 13, fontWeight: 700, cursor: "pointer" }}
        >
          Continue Shopping
        </button>
      </div>
    );
  }

  // ---- Empty cart ----
  if (items.length === 0 && step === 0) {
    return (
      <div className="p-6" style={{ maxWidth: 480, margin: "100px auto", textAlign: "center", color: "var(--foreground)" }}>
        <ShoppingCart size={40} style={{ color: "var(--muted-foreground)", margin: "0 auto 16px" }} />
        <h1 style={{ fontSize: 18, fontWeight: 700, marginBottom: 8 }}>Your cart is empty</h1>
        <p style={{ fontSize: 13, color: "var(--muted-foreground-2)", marginBottom: 20 }}>
          Add products from the shop to see them here.
        </p>
        <button
          onClick={onContinueShopping}
          style={{ padding: "11px 24px", background: "var(--primary)", border: "none", borderRadius: 50, color: "#fff", fontSize: 13, fontWeight: 700, cursor: "pointer" }}
        >
          Continue Shopping
        </button>
      </div>
    );
  }

  return (
    <>
      <AuthModal open={authOpen} onClose={() => setAuthOpen(false)} />
      <div style={{ maxWidth: 1280, margin: "0 auto", padding: "40px 32px", color: "var(--foreground)" }}>
      {/* Low-stock notice - real catalog stock, no fabricated viewer count or
          fake reservation timer (there's no reservation system behind this). */}
      {step === 0 && firstItem && liveActivity && liveActivity.stockLeft > 0 && liveActivity.stockLeft <= LOW_STOCK_THRESHOLD && (
        <div
          style={{
            background: "rgba(255,107,53,0.08)",
            border: "1px solid rgba(255,107,53,0.2)",
            borderRadius: 16,
            padding: "10px 16px",
            marginBottom: 20,
            display: "flex",
            alignItems: "center",
            gap: 10,
          }}
        >
          <AlertTriangle size={14} style={{ color: "#FF6B35", flexShrink: 0 }} />
          <p style={{ fontSize: 12, color: "#FF6B35" }}>
            Only <strong>{liveActivity.stockLeft} left</strong> in stock for {firstItem.name} - not reserved, so it's
            first come, first served.
          </p>
        </div>
      )}

      {/* Checkout stepper */}
      <div
        style={{
          background: "var(--card)",
          border: "1px solid rgba(var(--border-rgb),0.07)",
          borderRadius: 16,
          padding: "14px 20px",
          marginBottom: 20,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 0,
        }}
      >
        {steps.map((s, i) => (
          <div key={s} className="flex items-center">
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
              <div
                style={{
                  width: 28,
                  height: 28,
                  borderRadius: "50%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  background: i < step ? "#22C55E" : i === step ? "var(--primary)" : "var(--muted)",
                  border: i < step ? "none" : i === step ? "none" : "1px solid rgba(var(--border-rgb),0.1)",
                  fontSize: 11,
                  fontWeight: 700,
                  color: i <= step ? "#fff" : "var(--muted-foreground)",
                }}
              >
                {i < step ? <Check size={13} /> : i + 1}
              </div>
              <span style={{ fontSize: 10, color: i === step ? "var(--primary)" : "var(--muted-foreground)" }}>{s}</span>
            </div>
            {i < steps.length - 1 && (
              <div
                style={{
                  width: 80,
                  height: 1,
                  background: i < step ? "#22C55E" : "rgba(var(--border-rgb),0.08)",
                  margin: "0 8px",
                  marginBottom: 16,
                }}
              />
            )}
          </div>
        ))}
      </div>

      <div className="grid gap-6" style={{ gridTemplateColumns: "1fr 340px", alignItems: "start" }}>
        {/* Left column: step content */}
        <div className="space-y-4">
          {step === 0 && (
            <>
              <div style={{ background: "var(--card)", border: "1px solid rgba(var(--border-rgb),0.07)", borderRadius: 20, overflow: "hidden" }}>
                <div style={{ padding: "14px 20px", borderBottom: "1px solid rgba(var(--border-rgb),0.07)", display: "flex", alignItems: "center", gap: 8 }}>
                  <ShoppingCart size={15} style={{ color: "var(--primary)" }} />
                  <span style={{ fontSize: 14, fontWeight: 600 }}>Cart ({items.length} items)</span>
                </div>
                <div className="divide-y" style={{ borderColor: "rgba(var(--border-rgb),0.07)" }}>
                  {items.map(({ product, qty, billing }) => (
                    <div key={product.id} style={{ padding: "16px 20px", display: "flex", gap: 14 }}>
                      <img src={product.image} alt={product.name} style={{ width: 72, height: 72, objectFit: "cover", borderRadius: 8, flexShrink: 0 }} />
                      <div style={{ flex: 1 }}>
                        <p style={{ fontSize: 13, fontWeight: 600, marginBottom: 2 }}>{product.name}</p>
                        <p style={{ fontSize: 11, color: "var(--muted-foreground)", marginBottom: 8 }}>{product.category}</p>
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => updateQty(product.id, qty - 1)}
                            style={{ width: 24, height: 24, borderRadius: "50%", border: "1px solid rgba(var(--border-rgb),0.15)", background: "var(--muted)", color: "var(--foreground)", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center" }}
                          >
                            <Minus size={11} />
                          </button>
                          <span style={{ fontSize: 12, fontWeight: 600, minWidth: 16, textAlign: "center" }}>{qty}</span>
                          <button
                            onClick={() => updateQty(product.id, qty + 1)}
                            style={{ width: 24, height: 24, borderRadius: "50%", border: "1px solid rgba(var(--border-rgb),0.15)", background: "var(--muted)", color: "var(--foreground)", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center" }}
                          >
                            <Plus size={11} />
                          </button>
                        </div>
                      </div>
                      <div style={{ textAlign: "right", flexShrink: 0 }}>
                        <p style={{ fontSize: 16, fontWeight: 700, marginBottom: 2 }}>
                          {formatEUR(product.price * qty)}
                          {billing === "monthly" && (
                            <span style={{ fontSize: 11, fontWeight: 400, color: "var(--muted-foreground)" }}>/mo</span>
                          )}
                        </p>
                        <button
                          onClick={() => removeItem(product.id)}
                          style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted-foreground)", marginTop: 8 }}
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Bundle suggestions */}
              <div style={{ background: "var(--card)", border: "1px solid rgba(var(--border-rgb),0.07)", borderRadius: 20, overflow: "hidden" }}>
                <div style={{ padding: "14px 20px", borderBottom: "1px solid rgba(var(--border-rgb),0.07)", display: "flex", alignItems: "center", gap: 8 }}>
                  <Sparkles size={15} style={{ color: "var(--primary)" }} />
                  <span style={{ fontSize: 14, fontWeight: 600 }}>AI Recommends to Complete Your Setup</span>
                </div>
                <div style={{ padding: "12px 20px", display: "flex", flexDirection: "column", gap: 10 }}>
                  {bundlesLoading ? (
                    Array.from({ length: 2 }).map((_, i) => (
                      <div key={i} className="animate-pulse" style={{ height: 76, background: "var(--muted)", borderRadius: 16 }} />
                    ))
                  ) : bundles.length === 0 ? (
                    <p style={{ fontSize: 12, color: "var(--muted-foreground)" }}>No additional recommendations right now.</p>
                  ) : (
                    bundles.map((product) => {
                      const added = isInCart(product.id);
                      return (
                        <div key={product.id} style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px", background: "var(--muted)", borderRadius: 16, border: "1px solid rgba(var(--border-rgb),0.05)" }}>
                          <img src={product.image} alt={product.name} style={{ width: 52, height: 52, objectFit: "cover", borderRadius: 6, flexShrink: 0 }} />
                          <div style={{ flex: 1 }}>
                            <p style={{ fontSize: 12, fontWeight: 600, marginBottom: 2 }}>{product.name}</p>
                            <p style={{ fontSize: 10, color: "var(--muted-foreground)" }}>{product.reasons[0]}</p>
                          </div>
                          <div style={{ textAlign: "right", flexShrink: 0 }}>
                            <p style={{ fontSize: 14, fontWeight: 700, marginBottom: 6 }}>{formatEUR(product.price)}</p>
                            <button
                              onClick={() => (added ? removeItem(product.id) : addItem(product))}
                              style={{
                                padding: "6px 14px", borderRadius: 50, border: added ? "none" : "1px solid rgba(var(--primary-rgb),0.3)",
                                background: added ? "#22C55E" : "rgba(var(--primary-rgb),0.08)", color: added ? "#fff" : "var(--primary)",
                                fontSize: 11, fontWeight: 600, cursor: "pointer", display: "flex", alignItems: "center", gap: 4,
                              }}
                            >
                              {added ? <><Check size={10} /> Added</> : "+ Add"}
                            </button>
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            </>
          )}

          {step === 1 && (
            <div style={{ background: "var(--card)", border: "1px solid rgba(var(--border-rgb),0.07)", borderRadius: 20, padding: 24 }}>
              <p style={{ fontSize: 14, fontWeight: 600, marginBottom: 18 }}>Shipping Details</p>
              <div className="grid grid-cols-2 gap-4">
                <div style={{ gridColumn: "span 2" }}>
                  <label style={labelStyle}>Full name</label>
                  <input style={inputStyle} value={shipping.fullName} onChange={(e) => setShipping({ ...shipping, fullName: e.target.value })} placeholder="Jan Müller" />
                  {errors.fullName && <p style={errorStyle}>{errors.fullName}</p>}
                </div>
                <div style={{ gridColumn: "span 2" }}>
                  <label style={labelStyle}>Address</label>
                  <input style={inputStyle} value={shipping.address} onChange={(e) => setShipping({ ...shipping, address: e.target.value })} placeholder="Street and house number" />
                  {errors.address && <p style={errorStyle}>{errors.address}</p>}
                </div>
                <div>
                  <label style={labelStyle}>City</label>
                  <input style={inputStyle} value={shipping.city} onChange={(e) => setShipping({ ...shipping, city: e.target.value })} placeholder="Munich" />
                  {errors.city && <p style={errorStyle}>{errors.city}</p>}
                </div>
                <div>
                  <label style={labelStyle}>Postal code</label>
                  <input style={inputStyle} value={shipping.postalCode} onChange={(e) => setShipping({ ...shipping, postalCode: e.target.value })} placeholder="80331" />
                  {errors.postalCode && <p style={errorStyle}>{errors.postalCode}</p>}
                </div>
              </div>
            </div>
          )}

          {step === 2 && (
            <div style={{ background: "var(--card)", border: "1px solid rgba(var(--border-rgb),0.07)", borderRadius: 20, padding: 24 }}>
              <p style={{ fontSize: 14, fontWeight: 600, marginBottom: 18 }}>Payment</p>
              <div className="grid grid-cols-2 gap-4">
                <div style={{ gridColumn: "span 2" }}>
                  <label style={labelStyle}>Name on card</label>
                  <input style={inputStyle} value={payment.cardName} onChange={(e) => setPayment({ ...payment, cardName: e.target.value })} placeholder="Jan Müller" />
                  {errors.cardName && <p style={errorStyle}>{errors.cardName}</p>}
                </div>
                <div style={{ gridColumn: "span 2" }}>
                  <label style={labelStyle}>Card number</label>
                  <input style={inputStyle} value={payment.cardNumber} onChange={(e) => setPayment({ ...payment, cardNumber: e.target.value })} placeholder="4242 4242 4242 4242" maxLength={19} />
                  {errors.cardNumber && <p style={errorStyle}>{errors.cardNumber}</p>}
                </div>
                <div>
                  <label style={labelStyle}>Expiry (MM/YY)</label>
                  <input style={inputStyle} value={payment.expiry} onChange={(e) => setPayment({ ...payment, expiry: e.target.value })} placeholder="09/28" maxLength={5} />
                  {errors.expiry && <p style={errorStyle}>{errors.expiry}</p>}
                </div>
                <div>
                  <label style={labelStyle}>CVC</label>
                  <input style={inputStyle} value={payment.cvc} onChange={(e) => setPayment({ ...payment, cvc: e.target.value })} placeholder="123" maxLength={4} />
                  {errors.cvc && <p style={errorStyle}>{errors.cvc}</p>}
                </div>
              </div>
            </div>
          )}

          {step === 3 && (
            <div style={{ background: "var(--card)", border: "1px solid rgba(var(--border-rgb),0.07)", borderRadius: 20, padding: 24 }}>
              <p style={{ fontSize: 14, fontWeight: 600, marginBottom: 18 }}>Review & Confirm</p>
              <div className="space-y-4">
                <div>
                  <p style={{ fontSize: 11, color: "var(--muted-foreground)", marginBottom: 4 }}>SHIP TO</p>
                  <p style={{ fontSize: 13 }}>{shipping.fullName}</p>
                  <p style={{ fontSize: 13, color: "var(--muted-foreground-2)" }}>{shipping.address}, {shipping.city} {shipping.postalCode}</p>
                </div>
                <div>
                  <p style={{ fontSize: 11, color: "var(--muted-foreground)", marginBottom: 4 }}>PAYMENT</p>
                  <p style={{ fontSize: 13 }}>Card ending in {payment.cardNumber.replace(/\s/g, "").slice(-4)}</p>
                </div>
                <div>
                  <p style={{ fontSize: 11, color: "var(--muted-foreground)", marginBottom: 8 }}>ITEMS</p>
                  {items.map(({ product, qty, billing }) => (
                    <div key={product.id} className="flex justify-between" style={{ marginBottom: 4 }}>
                      <span style={{ fontSize: 12 }}>{product.name} × {qty}</span>
                      <span style={{ fontSize: 12 }}>
                        {formatEUR(product.price * qty)}
                        {billing === "monthly" && (
                          <span style={{ color: "var(--muted-foreground)" }}>/mo</span>
                        )}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {step > 0 && (
            <button
              onClick={() => setStep((s) => s - 1)}
              style={{ display: "flex", alignItems: "center", gap: 6, background: "none", border: "none", color: "var(--muted-foreground)", fontSize: 12, cursor: "pointer", padding: "4px 0" }}
            >
              <ChevronLeft size={14} /> Back
            </button>
          )}
        </div>

        {/* Right: Order summary */}
        <div className="space-y-4">
          <div style={{ background: "var(--card)", border: "1px solid rgba(var(--border-rgb),0.07)", borderRadius: 20, padding: "20px" }}>
            <p style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>Order Summary</p>
            <div className="space-y-3" style={{ marginBottom: 16 }}>
              {subtotal > 0 && (
                <div className="flex justify-between">
                  <span style={{ fontSize: 12, color: "var(--muted-foreground-2)" }}>
                    One-time{onetimeItemCount > 0 ? ` (${onetimeItemCount} item${onetimeItemCount === 1 ? "" : "s"})` : ""}
                  </span>
                  <span style={{ fontSize: 12 }}>{formatEUR(subtotal)}</span>
                </div>
              )}
              {monthlyTotal > 0 && (
                <div className="flex justify-between">
                  <span style={{ fontSize: 12, color: "var(--muted-foreground-2)" }}>Monthly charges</span>
                  <span style={{ fontSize: 12 }}>{formatEUR(monthlyTotal)}/mo</span>
                </div>
              )}
              {subtotal === 0 && monthlyTotal === 0 && (
                <div className="flex justify-between">
                  <span style={{ fontSize: 12, color: "var(--muted-foreground-2)" }}>Subtotal ({items.length} items)</span>
                  <span style={{ fontSize: 12 }}>{formatEUR(0)}</span>
                </div>
              )}
              {bundleDiscount > 0 && (
                <div className="flex justify-between">
                  <span style={{ fontSize: 12, color: "#22C55E", display: "flex", alignItems: "center", gap: 4 }}>
                    <Tag size={10} /> Bundle Discount (5%)
                  </span>
                  <span style={{ fontSize: 12, color: "#22C55E" }}>-{formatEUR(bundleDiscount)}</span>
                </div>
              )}
              <div className="flex justify-between">
                <span style={{ fontSize: 12, color: "var(--muted-foreground-2)" }}>Shipping</span>
                <span style={{ fontSize: 12, color: "#22C55E" }}>FREE</span>
              </div>
            </div>
            <div style={{ borderTop: "1px solid rgba(var(--border-rgb),0.07)", paddingTop: 12, marginBottom: 16 }}>
              {onetimeTotal > 0 && monthlyTotal > 0 ? (
                <>
                  <div className="flex justify-between" style={{ marginBottom: 6 }}>
                    <span style={{ fontSize: 13, fontWeight: 600 }}>Today</span>
                    <span style={{ fontSize: 16, fontWeight: 700 }}>{formatEUR(onetimeTotal)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span style={{ fontSize: 13, fontWeight: 600 }}>Monthly</span>
                    <span style={{ fontSize: 16, fontWeight: 700 }}>{formatEUR(monthlyTotal)}<span style={{ fontSize: 11, fontWeight: 400, color: "var(--muted-foreground)" }}>/mo</span></span>
                  </div>
                </>
              ) : monthlyTotal > 0 ? (
                <div className="flex justify-between">
                  <span style={{ fontSize: 14, fontWeight: 600 }}>Total</span>
                  <span style={{ fontSize: 18, fontWeight: 700 }}>{formatEUR(monthlyTotal)}<span style={{ fontSize: 12, fontWeight: 400, color: "var(--muted-foreground)" }}>/mo</span></span>
                </div>
              ) : (
                <div className="flex justify-between">
                  <span style={{ fontSize: 14, fontWeight: 600 }}>Total</span>
                  <span style={{ fontSize: 18, fontWeight: 700 }}>{formatEUR(onetimeTotal)}</span>
                </div>
              )}
            </div>

            <div className="grid grid-cols-3 gap-2 mb-4" style={{ marginTop: 16 }}>
              {[
                { icon: Shield, label: "2yr Warranty" },
                { icon: Truck, label: "Free Delivery" },
                { icon: Package, label: "Easy Returns" },
              ].map(({ icon: Icon, label }) => (
                <div key={label} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4, padding: "8px 4px", background: "var(--muted)", borderRadius: 8, border: "1px solid rgba(var(--border-rgb),0.05)" }}>
                  <Icon size={13} style={{ color: "var(--muted-foreground)" }} />
                  <span style={{ fontSize: 9, color: "var(--muted-foreground)", textAlign: "center" }}>{label}</span>
                </div>
              ))}
            </div>

            <button
              onClick={handleContinue}
              disabled={placingOrder}
              style={{
                width: "100%", padding: "13px", background: "var(--primary)", border: "none", borderRadius: 50,
                color: "#fff", fontSize: 14, fontWeight: 700, cursor: placingOrder ? "default" : "pointer",
                opacity: placingOrder ? 0.7 : 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
                transition: "background 0.2s",
              }}
              onMouseEnter={(e) => !placingOrder && ((e.currentTarget as HTMLButtonElement).style.background = "var(--primary-hover)")}
              onMouseLeave={(e) => !placingOrder && ((e.currentTarget as HTMLButtonElement).style.background = "var(--primary)")}
            >
              {placingOrder ? "Placing order…" : step < 3 ? "Continue to " + steps[step + 1] : "Place Order"}
              {!placingOrder && <ChevronRight size={16} />}
            </button>
          </div>
        </div>
      </div>
    </div>
    </>
  );
}
