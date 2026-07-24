import { useState, useRef, useEffect } from "react";
import {
  Send, Mic, MicOff, Sparkles, ShoppingCart, X, Minus,
  PanelLeftClose, PanelRightClose, Check, Info,
} from "lucide-react";
import { useCart } from "../cart/CartContext";
import { askAssistant } from "../api/mockApi";
import { formatEUR } from "../lib/format";
import { useSpeechRecognition } from "../lib/useSpeechRecognition";
import type { ChatMessage, Product } from "../types";

type DockSide = "left" | "right";

const initialMessages: ChatMessage[] = [
  {
    id: 1,
    role: "assistant",
    text: "Hi — I'm your OneShop assistant. Ask about phones, plans, bundles, or accessories and I'll find options from the catalog.",
    timestamp: "09:42",
  },
];

const suggestions = ["Show me plans", "Best camera phone", "Any bundle deals?", "Headphones"];

const DOCK_STORAGE_KEY = "oneshop-chat-dock";

const WhyPanel = ({ product, onClose }: { product: Product; onClose: () => void }) => (
  <div
    style={{
      background: "var(--surface)",
      border: "1px solid rgba(var(--primary-rgb),0.2)",
      borderRadius: 12,
      padding: "10px 12px",
      marginTop: 4,
    }}
  >
    <div className="flex items-center justify-between mb-2">
      <span style={{ fontSize: 10, fontWeight: 700, color: "var(--primary)", letterSpacing: "0.06em", textTransform: "uppercase" }}>
        Why recommended
      </span>
      <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted-foreground)", padding: 0, display: "flex" }}>
        <X size={12} />
      </button>
    </div>
    <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 6 }}>
      {product.reasons.slice(0, 3).map((reason, i) => (
        <li key={i} className="flex gap-2" style={{ fontSize: 11, color: "var(--foreground)", lineHeight: 1.45 }}>
          <Check size={11} style={{ color: "var(--primary)", flexShrink: 0, marginTop: 2 }} />
          {reason}
        </li>
      ))}
    </ul>
  </div>
);

export function FloatingChat() {
  const [open, setOpen] = useState(false);
  const [dock, setDock] = useState<DockSide>(() => {
    if (typeof window === "undefined") return "right";
    const stored = window.localStorage.getItem(DOCK_STORAGE_KEY);
    return stored === "left" || stored === "right" ? stored : "right";
  });
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
  const [input, setInput] = useState("");
  const [typing, setTyping] = useState(false);
  const [whyProductId, setWhyProductId] = useState<number | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const { addItem, isInCart } = useCart();

  const { listening, supported: micSupported, toggleListening } = useSpeechRecognition((transcript) => {
    setInput((prev) => (prev ? `${prev} ${transcript}` : transcript));
  });

  useEffect(() => {
    window.localStorage.setItem(DOCK_STORAGE_KEY, dock);
  }, [dock]);

  useEffect(() => {
    if (open) bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, typing, open]);

  const send = (text: string) => {
    if (!text.trim() || typing) return;
    const userMsg: ChatMessage = {
      id: Date.now(),
      role: "user",
      text,
      timestamp: new Date().toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setTyping(true);
    setWhyProductId(null);

    askAssistant(text)
      .then(({ reply, products }) => {
        setMessages((prev) => [
          ...prev,
          {
            id: Date.now() + 1,
            role: "assistant",
            text: reply,
            products,
            timestamp: new Date().toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }),
          },
        ]);
      })
      .catch(() => {
        setMessages((prev) => [
          ...prev,
          {
            id: Date.now() + 1,
            role: "assistant",
            text: "Sorry, I couldn't reach the recommendation service. Please try again.",
            timestamp: new Date().toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }),
          },
        ]);
      })
      .finally(() => setTyping(false));
  };

  const sideStyle = dock === "right" ? { right: 20 } : { left: 20 };

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        aria-label="Open AI shopping assistant"
        style={{
          position: "fixed",
          bottom: 20,
          ...sideStyle,
          width: 56,
          height: 56,
          borderRadius: "50%",
          border: "none",
          cursor: "pointer",
          background: "linear-gradient(135deg, var(--primary), #7B61FF)",
          boxShadow: "0 8px 24px rgba(var(--primary-rgb), 0.45)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          zIndex: 998,
          opacity: open ? 0 : 1,
          transform: open ? "scale(0.6)" : "scale(1)",
          pointerEvents: open ? "none" : "auto",
          transition: "opacity 0.2s ease, transform 0.2s ease",
        }}
      >
        <Sparkles size={22} style={{ color: "#fff" }} />
        <span
          style={{
            position: "absolute",
            inset: 0,
            borderRadius: "50%",
            border: "2px solid var(--primary)",
            animation: "chat-pulse 2.2s ease-out infinite",
          }}
        />
      </button>

      <div
        role="dialog"
        aria-label="AI shopping assistant"
        style={{
          position: "fixed",
          bottom: 20,
          ...sideStyle,
          width: "min(380px, calc(100vw - 32px))",
          height: "min(620px, calc(100vh - 48px))",
          background: "var(--card)",
          border: "1px solid var(--border)",
          borderRadius: 20,
          boxShadow: "0 16px 48px rgba(0,0,0,0.2)",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          zIndex: 999,
          opacity: open ? 1 : 0,
          transform: open ? "translateY(0) scale(1)" : "translateY(16px) scale(0.97)",
          pointerEvents: open ? "auto" : "none",
          transition: "opacity 0.2s ease, transform 0.2s ease",
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: "14px 16px",
            borderBottom: "1px solid var(--border)",
            display: "flex",
            alignItems: "center",
            gap: 10,
            flexShrink: 0,
            background: "var(--surface)",
          }}
        >
          <div
            style={{
              width: 30,
              height: 30,
              borderRadius: "50%",
              background: "linear-gradient(135deg, var(--primary), #7B61FF)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            <Sparkles size={14} style={{ color: "#fff" }} />
          </div>
          <div style={{ minWidth: 0 }}>
            <p style={{ fontSize: 13, fontWeight: 700, color: "var(--foreground)" }}>OneShop Assistant</p>
            <p style={{ fontSize: 10.5, color: "var(--muted-foreground)" }}>Personalized product help</p>
          </div>
          <div style={{ marginLeft: "auto", display: "flex", gap: 2, flexShrink: 0 }}>
            <button
              onClick={() => setDock((d) => (d === "right" ? "left" : "right"))}
              title={dock === "right" ? "Move to left side" : "Move to right side"}
              style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted-foreground)", padding: 6, display: "flex", borderRadius: 8 }}
            >
              {dock === "right" ? <PanelLeftClose size={15} /> : <PanelRightClose size={15} />}
            </button>
            <button
              onClick={() => setOpen(false)}
              title="Minimize"
              style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted-foreground)", padding: 6, display: "flex", borderRadius: 8 }}
            >
              <Minus size={15} />
            </button>
            <button
              onClick={() => setOpen(false)}
              title="Close"
              style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted-foreground)", padding: 6, display: "flex", borderRadius: 8 }}
            >
              <X size={15} />
            </button>
          </div>
        </div>

        {/* Messages */}
        <div style={{ flex: 1, overflowY: "auto", padding: "16px", display: "flex", flexDirection: "column", gap: 12 }}>
          {messages.map((msg) => (
            <div
              key={msg.id}
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: msg.role === "user" ? "flex-end" : "flex-start",
                gap: 6,
              }}
            >
              <div
                style={{
                  maxWidth: "88%",
                  padding: "10px 14px",
                  borderRadius: msg.role === "user" ? 16 : 16,
                  background: msg.role === "user" ? "var(--primary)" : "var(--muted)",
                  border: msg.role === "assistant" ? "1px solid var(--border)" : "none",
                  fontSize: 12.5,
                  color: msg.role === "user" ? "#fff" : "var(--foreground)",
                  lineHeight: 1.55,
                  whiteSpace: "pre-wrap",
                }}
              >
                {msg.text}
              </div>

              {msg.products && msg.products.length > 0 && (
                <div className="flex gap-2.5" style={{ flexWrap: "nowrap", overflowX: "auto", paddingBottom: 2, maxWidth: "100%" }}>
                  {msg.products.map((p) => {
                    const added = isInCart(p.id);
                    const showWhy = whyProductId === p.id;
                    return (
                      <div
                        key={p.id}
                        style={{
                          background: "var(--card)",
                          border: "1px solid var(--border)",
                          borderRadius: 16,
                          padding: 10,
                          minWidth: 140,
                          flexShrink: 0,
                        }}
                      >
                        <img
                          src={p.image}
                          alt={p.name}
                          style={{ width: "100%", height: 76, objectFit: "cover", borderRadius: 10, marginBottom: 8 }}
                        />
                        <p style={{ fontSize: 11, fontWeight: 600, color: "var(--foreground)", marginBottom: 4, lineHeight: 1.3 }}>{p.name}</p>
                        <div className="flex items-center justify-between mb-2">
                          <span style={{ fontSize: 12, fontWeight: 700, color: "var(--foreground)" }}>{formatEUR(p.price)}</span>
                          <span style={{ fontSize: 9, fontWeight: 700, color: "var(--primary)", background: "rgba(var(--primary-rgb),0.1)", padding: "2px 6px", borderRadius: 20 }}>
                            {p.aiScore}% match
                          </span>
                        </div>
                        <div className="flex gap-1.5">
                          <button
                            onClick={() => addItem(p)}
                            disabled={added}
                            style={{
                              flex: 1,
                              padding: "6px 8px",
                              background: added ? "var(--muted-foreground)" : "var(--primary)",
                              border: "none",
                              borderRadius: 50,
                              color: "#fff",
                              fontSize: 10,
                              fontWeight: 600,
                              cursor: added ? "default" : "pointer",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              gap: 3,
                            }}
                          >
                            {added ? <><Check size={10} /> Added</> : <><ShoppingCart size={10} /> Add</>}
                          </button>
                          <button
                            onClick={() => setWhyProductId(showWhy ? null : p.id)}
                            title="Why this recommendation?"
                            style={{
                              padding: "6px 8px",
                              background: "transparent",
                              border: "1.5px solid rgba(var(--primary-rgb),0.3)",
                              borderRadius: 50,
                              color: "var(--primary)",
                              cursor: "pointer",
                              display: "flex",
                              alignItems: "center",
                            }}
                          >
                            <Info size={11} />
                          </button>
                        </div>
                        {showWhy && <WhyPanel product={p} onClose={() => setWhyProductId(null)} />}
                      </div>
                    );
                  })}
                </div>
              )}

              <span style={{ fontSize: 9, color: "var(--muted-foreground)" }}>{msg.timestamp}</span>
            </div>
          ))}

          {typing && (
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <div
                style={{
                  background: "var(--muted)",
                  border: "1px solid var(--border)",
                  borderRadius: 16,
                  padding: "10px 14px",
                  display: "flex",
                  gap: 4,
                  alignItems: "center",
                }}
              >
                {[0, 1, 2].map((i) => (
                  <span
                    key={i}
                    style={{
                      width: 5,
                      height: 5,
                      borderRadius: "50%",
                      background: "var(--primary)",
                      display: "block",
                      animation: `chat-bounce 1.2s ${i * 0.2}s infinite`,
                    }}
                  />
                ))}
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Suggestions */}
        <div style={{ padding: "8px 14px", borderTop: "1px solid var(--border)", display: "flex", gap: 6, flexWrap: "nowrap", overflowX: "auto" }}>
          {suggestions.map((s) => (
            <button
              key={s}
              onClick={() => send(s)}
              disabled={typing}
              style={{
                padding: "6px 12px",
                borderRadius: 50,
                border: "1.5px solid var(--border)",
                background: "transparent",
                color: "var(--foreground)",
                fontSize: 11,
                fontWeight: 600,
                cursor: typing ? "default" : "pointer",
                whiteSpace: "nowrap",
                flexShrink: 0,
                opacity: typing ? 0.5 : 1,
              }}
            >
              {s}
            </button>
          ))}
        </div>

        {/* Input */}
        <div style={{ padding: "10px 14px 14px", borderTop: "1px solid var(--border)", display: "flex", gap: 8, flexShrink: 0 }}>
          <div style={{ flex: 1, position: "relative" }}>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && send(input)}
              placeholder="Ask about products, plans, bundles..."
              style={{
                width: "100%",
                background: "var(--input-background)",
                border: "1.5px solid rgba(var(--primary-rgb),0.25)",
                borderRadius: 50,
                padding: "9px 38px 9px 14px",
                fontSize: 12,
                color: "var(--foreground)",
                outline: "none",
              }}
            />
            <button
              onClick={toggleListening}
              disabled={!micSupported}
              title={micSupported ? "Voice input" : "Voice input not supported in this browser"}
              style={{
                position: "absolute",
                right: 6,
                top: "50%",
                transform: "translateY(-50%)",
                background: listening ? "rgba(var(--primary-rgb),0.15)" : "transparent",
                border: "none",
                cursor: micSupported ? "pointer" : "not-allowed",
                opacity: micSupported ? 1 : 0.4,
                color: listening ? "var(--primary)" : "var(--muted-foreground)",
                padding: 4,
                borderRadius: 50,
                display: "flex",
              }}
            >
              {listening ? <MicOff size={13} /> : <Mic size={13} />}
            </button>
          </div>
          <button
            onClick={() => send(input)}
            disabled={typing || !input.trim()}
            style={{
              padding: "9px 14px",
              background: "var(--primary)",
              border: "none",
              borderRadius: 50,
              color: "#fff",
              cursor: typing || !input.trim() ? "default" : "pointer",
              opacity: typing || !input.trim() ? 0.5 : 1,
              display: "flex",
              alignItems: "center",
              flexShrink: 0,
            }}
          >
            <Send size={14} />
          </button>
        </div>
      </div>

      <style>{`
        @keyframes chat-bounce {
          0%, 80%, 100% { transform: scale(0); opacity: 0.4; }
          40% { transform: scale(1); opacity: 1; }
        }
        @keyframes chat-pulse {
          0% { opacity: 0.6; transform: scale(1); }
          100% { opacity: 0; transform: scale(1.35); }
        }
      `}</style>
    </>
  );
}
