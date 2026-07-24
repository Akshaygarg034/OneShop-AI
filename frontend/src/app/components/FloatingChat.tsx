import { useState, useRef, useEffect, useCallback } from "react";
import {
  Send, Mic, MicOff, Sparkles, ShoppingCart, X,
  Maximize2, Minimize2, Check,
} from "lucide-react";
import { useCart } from "../cart/CartContext";
import { useAuth } from "../auth/AuthContext";
import { askAssistant } from "../api/mockApi";
import { formatEUR } from "../lib/format";
import { useSpeechRecognition } from "../lib/useSpeechRecognition";
import { AuthModal } from "./AuthModal";
import type { ChatMessage, Product } from "../types";

type DockSide = "left" | "right";
type ChatSize = "compact" | "expanded";

const DOCK_KEY = "oneshop-chat-dock";

const WELCOME: ChatMessage = {
  id: 1,
  role: "assistant",
  text: "Hi — I'm your OneShop AI assistant. Ask about phones, plans, bundles, or accessories and I'll find the best match for you.",
  timestamp: new Date().toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }),
};

const CHIPS = ["Show me plans", "Best camera phone", "Bundle deals", "Headphones"];

// ─── Typing indicator ──────────────────────────────────────────────────────────
function TypingIndicator() {
  return (
    <div style={{ display: "flex", paddingTop: 2 }}>
      <div
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 4,
          padding: "10px 14px",
          background: "var(--muted)",
          borderRadius: "4px 14px 14px 14px",
        }}
      >
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            style={{
              width: 5,
              height: 5,
              borderRadius: "50%",
              background: "var(--muted-foreground)",
              animation: `dot-bounce 1.3s ${i * 0.18}s ease-in-out infinite`,
            }}
          />
        ))}
      </div>
    </div>
  );
}

// ─── Product card ──────────────────────────────────────────────────────────────
function ProductCard({
  product,
  expanded,
  onAdd,
  onWhy,
  inCart,
  whyOpen,
  showWhy,
}: {
  product: Product;
  expanded: boolean;
  onAdd: () => void;
  onWhy: () => void;
  inCart: boolean;
  whyOpen: boolean;
  showWhy: boolean;
}) {
  const hasWhy = showWhy && product.reasons.length > 0;

  return (
    <div
      style={{
        background: "var(--card)",
        border: "1px solid var(--border)",
        borderRadius: 12,
        overflow: "hidden",
        // compact: fixed 168px width in a horizontal scroll
        // expanded: fill half the row (2-column grid)
        flexShrink: expanded ? undefined : 0,
        flex: expanded ? "1 1 calc(50% - 4px)" : undefined,
        width: expanded ? undefined : 168,
        minWidth: expanded ? 172 : 168,
        maxWidth: expanded ? "calc(50% - 4px)" : 168,
        boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
        transition: "box-shadow 0.2s",
      }}
      onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.boxShadow = "0 4px 16px rgba(0,0,0,0.09)"; }}
      onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.boxShadow = "0 1px 3px rgba(0,0,0,0.04)"; }}
    >
      {/* Product image — no overlay badges */}
      <div
        style={{
          height: expanded ? 126 : 96,
          overflow: "hidden",
          background: "var(--muted)",
        }}
      >
        <img
          src={product.image}
          alt={product.name}
          style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
        />
      </div>

      <div style={{ padding: "10px 11px 12px" }}>
        {/* Category */}
        <p
          style={{
            fontSize: 9,
            fontWeight: 700,
            color: "var(--muted-foreground)",
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            marginBottom: 3,
          }}
        >
          {product.category}
        </p>

        {/* Name */}
        <p
          style={{
            fontSize: 12,
            fontWeight: 600,
            color: "var(--foreground)",
            lineHeight: 1.35,
            marginBottom: 5,
            overflow: "hidden",
            display: "-webkit-box",
            WebkitLineClamp: 2,
            WebkitBoxOrient: "vertical",
          }}
        >
          {product.name}
        </p>

        {/* Price */}
        <div style={{ marginBottom: 9 }}>
          <span style={{ fontSize: expanded ? 14 : 13, fontWeight: 700, color: "var(--foreground)" }}>
            {formatEUR(product.price)}
          </span>
          {product.monthlyPrice > 0 && (
            <span
              style={{
                fontSize: 9.5,
                fontWeight: 400,
                color: "var(--muted-foreground)",
                marginLeft: 5,
              }}
            >
              or {formatEUR(product.monthlyPrice)}/mo
            </span>
          )}
        </div>

        {/* Primary CTA */}
        <button
          onClick={onAdd}
          disabled={inCart}
          style={{
            width: "100%",
            padding: expanded ? "8px 10px" : "7px 10px",
            background: inCart ? "#16A34A" : "var(--primary)",
            border: "none",
            borderRadius: 8,
            color: "#fff",
            fontSize: 11,
            fontWeight: 600,
            cursor: inCart ? "default" : "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 5,
            letterSpacing: "0.01em",
            transition: "opacity 0.15s",
          }}
          onMouseEnter={(e) => { if (!inCart) (e.currentTarget as HTMLElement).style.opacity = "0.88"; }}
          onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.opacity = "1"; }}
        >
          {inCart ? (
            <><Check size={11} />Added to cart</>
          ) : (
            <><ShoppingCart size={11} />Add to cart</>
          )}
        </button>

        {/* Why — text link, not an icon button */}
        {hasWhy && (
          <button
            onClick={onWhy}
            style={{
              width: "100%",
              marginTop: 7,
              background: "none",
              border: "none",
              padding: "2px 0",
              cursor: "pointer",
              fontSize: 10,
              color: whyOpen ? "var(--primary)" : "var(--muted-foreground)",
              fontWeight: 500,
              textAlign: "center",
              textDecoration: "underline",
              textUnderlineOffset: "2px",
              textDecorationColor: "currentColor",
              transition: "color 0.15s",
            }}
          >
            {whyOpen ? "Hide explanation" : "Why this recommendation?"}
          </button>
        )}

        {/* Why panel */}
        {whyOpen && hasWhy && (
          <div
            style={{
              marginTop: 8,
              padding: "8px 10px",
              background: "rgba(var(--primary-rgb),0.05)",
              borderRadius: 8,
              borderLeft: "2px solid var(--primary)",
              animation: "why-in 0.14s ease-out",
            }}
          >
            {product.reasons.slice(0, 2).map((reason, i) => (
              <div
                key={i}
                style={{
                  display: "flex",
                  gap: 5,
                  fontSize: 10,
                  color: "var(--foreground)",
                  lineHeight: 1.5,
                  marginTop: i > 0 ? 4 : 0,
                }}
              >
                <Check size={9} style={{ color: "var(--primary)", flexShrink: 0, marginTop: 2 }} />
                {reason}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Small icon button for the header ─────────────────────────────────────────
function IconBtn({
  children,
  title,
  onClick,
  danger = false,
}: {
  children: React.ReactNode;
  title: string;
  onClick: () => void;
  danger?: boolean;
}) {
  const [hov, setHov] = useState(false);
  return (
    <button
      title={title}
      onClick={onClick}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        width: 28,
        height: 28,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: hov ? (danger ? "rgba(239,68,68,0.1)" : "var(--muted)") : "none",
        border: "none",
        borderRadius: 7,
        cursor: "pointer",
        color: hov && danger ? "#EF4444" : "var(--muted-foreground)",
        transition: "background 0.12s, color 0.12s",
      }}
    >
      {children}
    </button>
  );
}

// ─── Chip for dock toggle ──────────────────────────────────────────────────────
const DockIcon = ({ toLeft }: { toLeft: boolean }) => (
  <svg
    width="14"
    height="14"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <rect x="3" y="3" width="18" height="18" rx="2" />
    {toLeft ? <path d="M9 3v18" /> : <path d="M15 3v18" />}
  </svg>
);

// ─── Main component ────────────────────────────────────────────────────────────
export function FloatingChat() {
  const [open, setOpen] = useState(false);
  const [size, setSize] = useState<ChatSize>("compact");
  const [dock, setDock] = useState<DockSide>(() => {
    if (typeof window === "undefined") return "right";
    return (localStorage.getItem(DOCK_KEY) as DockSide) === "left" ? "left" : "right";
  });
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME]);
  const [input, setInput] = useState("");
  const [typing, setTyping] = useState(false);
  const [whyId, setWhyId] = useState<string | null>(null);
  const [authOpen, setAuthOpen] = useState(false);

  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const { addItem, isInCart } = useCart();
  const { user } = useAuth();
  const { listening, supported: micSupported, toggleListening } = useSpeechRecognition((t) =>
    setInput((prev) => (prev ? `${prev} ${t}` : t)),
  );

  useEffect(() => { localStorage.setItem(DOCK_KEY, dock); }, [dock]);

  useEffect(() => {
    if (open) setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
  }, [messages, typing, open]);

  useEffect(() => {
    if (size === "expanded")
      setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 320);
  }, [size]);

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 260);
  }, [open]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      if (size === "expanded") setSize("compact");
      else setOpen(false);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [size]);

  const handleAdd = useCallback(
    (p: Product) => {
      if (!user) { setAuthOpen(true); return; }
      addItem(p);
    },
    [user, addItem],
  );

  const send = (text: string) => {
    if (!text.trim() || typing) return;
    const ts = new Date().toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
    setMessages((prev) => [...prev, { id: Date.now(), role: "user", text, timestamp: ts }]);
    setInput("");
    setTyping(true);
    setWhyId(null);

    askAssistant(text)
      .then(({ reply, products }) =>
        setMessages((prev) => [
          ...prev,
          {
            id: Date.now() + 1,
            role: "assistant",
            text: reply,
            products,
            timestamp: new Date().toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }),
          },
        ]),
      )
      .catch(() =>
        setMessages((prev) => [
          ...prev,
          {
            id: Date.now() + 1,
            role: "assistant",
            text: "Sorry, I couldn't reach the service right now. Please try again.",
            timestamp: new Date().toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }),
          },
        ]),
      )
      .finally(() => setTyping(false));
  };

  const isExp = size === "expanded";
  const side = dock === "right" ? { right: 24 } : { left: 24 };

  return (
    <>
      {/* ── FAB ──────────────────────────────────────────────────────────────── */}
      <button
        onClick={() => setOpen(true)}
        aria-label="Open AI shopping assistant"
        style={{
          position: "fixed",
          bottom: 24,
          ...side,
          width: 54,
          height: 54,
          borderRadius: "50%",
          border: "none",
          cursor: "pointer",
          background: "linear-gradient(145deg, var(--primary) 0%, #7C3AED 100%)",
          boxShadow:
            "0 2px 8px rgba(0,0,0,.12), 0 6px 20px rgba(var(--primary-rgb),.45)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          zIndex: 998,
          opacity: open ? 0 : 1,
          transform: open ? "scale(0.72)" : "scale(1)",
          pointerEvents: open ? "none" : "auto",
          transition: "opacity 0.2s ease, transform 0.2s ease",
        }}
      >
        <Sparkles size={20} color="#fff" />
        <span
          style={{
            position: "absolute",
            inset: -6,
            borderRadius: "50%",
            border: "1.5px solid rgba(var(--primary-rgb),.35)",
            animation: "fab-ring 2.6s ease-out infinite",
          }}
        />
      </button>

      {/* ── Chat panel ───────────────────────────────────────────────────────── */}
      <div
        role="dialog"
        aria-label="AI shopping assistant"
        style={{
          position: "fixed",
          bottom: 24,
          ...side,
          width: isExp ? "min(660px, calc(100vw - 24px))" : "min(392px, calc(100vw - 24px))",
          height: isExp
            ? "min(840px, calc(100vh - 40px))"
            : "min(640px, calc(100vh - 48px))",
          background: "var(--card)",
          borderRadius: 20,
          // Layered shadow: border ring + depth shadows
          boxShadow:
            "0 0 0 1px rgba(0,0,0,.06), 0 4px 12px rgba(0,0,0,.06), 0 16px 48px rgba(0,0,0,.12)",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          zIndex: 999,
          opacity: open ? 1 : 0,
          transform: open ? "translateY(0) scale(1)" : "translateY(10px) scale(0.98)",
          pointerEvents: open ? "auto" : "none",
          transition: [
            "opacity 0.22s ease",
            "transform 0.22s ease",
            "width 0.28s cubic-bezier(0.4,0,0.2,1)",
            "height 0.28s cubic-bezier(0.4,0,0.2,1)",
          ].join(", "),
        }}
      >
        {/* ── Header ─────────────────────────────────────────────────────────── */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            padding: "12px 12px 12px 16px",
            borderBottom: "1px solid var(--border)",
            flexShrink: 0,
          }}
        >
          {/* Avatar with live green dot */}
          <div style={{ position: "relative", flexShrink: 0 }}>
            <div
              style={{
                width: 36,
                height: 36,
                borderRadius: "50%",
                background: "linear-gradient(145deg, var(--primary) 0%, #7C3AED 100%)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Sparkles size={15} color="#fff" />
            </div>
            {/* Online indicator */}
            <span
              style={{
                position: "absolute",
                bottom: 0,
                right: 0,
                width: 9,
                height: 9,
                borderRadius: "50%",
                background: "#22C55E",
                border: "2px solid var(--card)",
              }}
            />
          </div>

          {/* Identity */}
          <div style={{ flex: 1, minWidth: 0 }}>
            <div
              style={{
                fontSize: 13.5,
                fontWeight: 700,
                color: "var(--foreground)",
                lineHeight: 1,
                letterSpacing: "-0.01em",
              }}
            >
              OneShop AI
            </div>
            <div
              style={{
                fontSize: 11,
                color: "var(--muted-foreground)",
                marginTop: 3,
                lineHeight: 1,
              }}
            >
              Shopping assistant
            </div>
          </div>

          {/* Actions — 3 max */}
          <div style={{ display: "flex", gap: 1 }}>
            <IconBtn
              title={dock === "right" ? "Move to left" : "Move to right"}
              onClick={() => setDock((d) => (d === "right" ? "left" : "right"))}
            >
              <DockIcon toLeft={dock === "right"} />
            </IconBtn>
            <IconBtn
              title={isExp ? "Compact view (Esc)" : "Expand"}
              onClick={() => setSize((s) => (s === "compact" ? "expanded" : "compact"))}
            >
              {isExp ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
            </IconBtn>
            <IconBtn
              danger
              title="Close"
              onClick={() => { setOpen(false); setSize("compact"); }}
            >
              <X size={14} />
            </IconBtn>
          </div>
        </div>

        {/* ── Messages ───────────────────────────────────────────────────────── */}
        <div
          style={{
            flex: 1,
            overflowY: "auto",
            padding: isExp ? "20px 20px" : "16px 16px",
            display: "flex",
            flexDirection: "column",
            gap: 18,
            // hide scrollbar on all browsers
            scrollbarWidth: "none",
            msOverflowStyle: "none",
          }}
        >
          {messages.map((msg) => (
            <div
              key={msg.id}
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: msg.role === "user" ? "flex-end" : "flex-start",
                gap: 4,
                animation: "msg-in 0.16s ease-out",
              }}
            >
              {msg.role === "assistant" ? (
                // Assistant: NO bubble — clean reading line
                <div
                  style={{
                    maxWidth: isExp ? "80%" : "90%",
                    fontSize: 13,
                    color: "var(--foreground)",
                    lineHeight: 1.65,
                    whiteSpace: "pre-wrap",
                  }}
                >
                  {msg.text}
                </div>
              ) : (
                // User: solid primary bubble
                <div
                  style={{
                    maxWidth: isExp ? "76%" : "86%",
                    padding: "10px 14px",
                    borderRadius: "16px 16px 3px 16px",
                    background: "var(--primary)",
                    fontSize: 13,
                    color: "#fff",
                    lineHeight: 1.6,
                    whiteSpace: "pre-wrap",
                  }}
                >
                  {msg.text}
                </div>
              )}

              {/* Product cards */}
              {msg.products && msg.products.length > 0 && (
                <div
                  style={{
                    display: "flex",
                    flexWrap: isExp ? "wrap" : "nowrap",
                    gap: 8,
                    overflowX: isExp ? "visible" : "auto",
                    paddingBottom: isExp ? 0 : 4,
                    maxWidth: "100%",
                    width: "100%",
                    marginTop: 6,
                    // hide horizontal scrollbar
                    scrollbarWidth: "none",
                    msOverflowStyle: "none",
                  }}
                >
                  {msg.products.map((p) => (
                    <ProductCard
                      key={p.id}
                      product={p}
                      expanded={isExp}
                      onAdd={() => handleAdd(p)}
                      onWhy={() => setWhyId((id) => (id === p.id ? null : p.id))}
                      inCart={isInCart(p.id)}
                      whyOpen={whyId === p.id}
                      showWhy={!!user}
                    />
                  ))}
                </div>
              )}

              <span
                style={{
                  fontSize: 9.5,
                  color: "var(--muted-foreground)",
                  opacity: 0.7,
                  marginTop: 2,
                }}
              >
                {msg.timestamp}
              </span>
            </div>
          ))}

          {typing && <TypingIndicator />}
          <div ref={bottomRef} />
        </div>

        {/* ── Suggestion chips ───────────────────────────────────────────────── */}
        <div
          style={{
            padding: "8px 16px",
            borderTop: "1px solid var(--border)",
            display: "flex",
            gap: 6,
            flexWrap: isExp ? "wrap" : "nowrap",
            overflowX: isExp ? "visible" : "auto",
            scrollbarWidth: "none",
            msOverflowStyle: "none",
          }}
        >
          {CHIPS.map((chip) => (
            <ChipBtn key={chip} label={chip} disabled={typing} onClick={() => send(chip)} />
          ))}
        </div>

        {/* ── Input area ─────────────────────────────────────────────────────── */}
        <div style={{ padding: "10px 14px 16px", flexShrink: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{ flex: 1, position: "relative" }}>
              <input
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && send(input)}
                placeholder="Ask about products, plans, bundles…"
                style={{
                  width: "100%",
                  padding: micSupported ? "10px 40px 10px 14px" : "10px 14px",
                  background: "var(--input-background)",
                  border: "1.5px solid var(--border)",
                  borderRadius: 12,
                  fontSize: 13,
                  color: "var(--foreground)",
                  outline: "none",
                  transition: "border-color 0.15s, box-shadow 0.15s",
                }}
                onFocus={(e) => {
                  e.target.style.borderColor = "var(--primary)";
                  e.target.style.boxShadow = "0 0 0 3px rgba(var(--primary-rgb),.1)";
                }}
                onBlur={(e) => {
                  e.target.style.borderColor = "var(--border)";
                  e.target.style.boxShadow = "none";
                }}
              />
              {micSupported && (
                <button
                  onClick={toggleListening}
                  title={listening ? "Stop listening" : "Voice input"}
                  style={{
                    position: "absolute",
                    right: 10,
                    top: "50%",
                    transform: "translateY(-50%)",
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                    padding: 4,
                    display: "flex",
                    borderRadius: 6,
                    color: listening ? "var(--primary)" : "var(--muted-foreground)",
                    transition: "color 0.15s",
                  }}
                >
                  {listening ? <MicOff size={15} /> : <Mic size={15} />}
                </button>
              )}
            </div>

            {/* Send — circle, gradient when active */}
            <button
              onClick={() => send(input)}
              disabled={typing || !input.trim()}
              style={{
                width: 40,
                height: 40,
                flexShrink: 0,
                border: "none",
                borderRadius: "50%",
                cursor: typing || !input.trim() ? "default" : "pointer",
                background:
                  typing || !input.trim()
                    ? "var(--muted)"
                    : "linear-gradient(145deg, var(--primary) 0%, #7C3AED 100%)",
                color: typing || !input.trim() ? "var(--muted-foreground)" : "#fff",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                boxShadow:
                  typing || !input.trim()
                    ? "none"
                    : "0 2px 8px rgba(var(--primary-rgb),.4)",
                transition: "background 0.18s, box-shadow 0.18s, color 0.18s",
              }}
            >
              <Send size={15} />
            </button>
          </div>
        </div>
      </div>

      <AuthModal open={authOpen} onClose={() => setAuthOpen(false)} />

      <style>{`
        @keyframes dot-bounce {
          0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
          30% { transform: translateY(-5px); opacity: 1; }
        }
        @keyframes fab-ring {
          0%   { transform: scale(1); opacity: 0.7; }
          100% { transform: scale(1.65); opacity: 0; }
        }
        @keyframes msg-in {
          from { opacity: 0; transform: translateY(5px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes why-in {
          from { opacity: 0; transform: scaleY(0.92); transform-origin: top; }
          to   { opacity: 1; transform: scaleY(1); }
        }
        /* Hide webkit scrollbar in messages and chip rows */
        div::-webkit-scrollbar { display: none; }
      `}</style>
    </>
  );
}

// ─── Suggestion chip ───────────────────────────────────────────────────────────
function ChipBtn({ label, disabled, onClick }: { label: string; disabled: boolean; onClick: () => void }) {
  const [hov, setHov] = useState(false);
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        flexShrink: 0,
        padding: "5px 11px",
        borderRadius: 9999,
        border: `1px solid ${hov && !disabled ? "var(--primary)" : "var(--border)"}`,
        background: hov && !disabled ? "rgba(var(--primary-rgb),.05)" : "transparent",
        color: hov && !disabled ? "var(--primary)" : "var(--foreground)",
        fontSize: 11.5,
        fontWeight: 500,
        cursor: disabled ? "default" : "pointer",
        opacity: disabled ? 0.4 : 1,
        whiteSpace: "nowrap",
        transition: "border-color 0.14s, background 0.14s, color 0.14s",
      }}
    >
      {label}
    </button>
  );
}
