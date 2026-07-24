import { useState, useRef, useEffect } from "react";
import {
  Send, Mic, MicOff, Sparkles, ShoppingCart, X, Minus,
  PanelLeftClose, PanelRightClose, Bot, User, Check,
} from "lucide-react";
import { useCart } from "../cart/CartContext";
import { askAssistant } from "../api/mockApi";
import { formatEUR } from "../lib/format";
import { useSpeechRecognition } from "../lib/useSpeechRecognition";
import type { ChatMessage } from "../types";

type DockSide = "left" | "right";

const initialMessages: ChatMessage[] = [
  {
    id: 1,
    role: "assistant",
    text: "Hi! 👋 I'm your AI shopping assistant. Ask me about phones, plans, bundles, or accessories and I'll pull matching options from the catalog.",
    timestamp: "09:42",
  },
];

const suggestions = ["Show me plans", "Best camera phone", "Any bundle deals?", "Headphones"];

const DOCK_STORAGE_KEY = "oneshop-chat-dock";

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
          borderRadius: 16,
          boxShadow: "0 20px 60px rgba(0,0,0,0.35)",
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
            padding: "12px 14px",
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
            <p style={{ fontSize: 12.5, fontWeight: 600, color: "var(--foreground)" }}>OneShop AI Assistant</p>
            <p style={{ fontSize: 10, color: "#22C55E" }}>● Online now</p>
          </div>
          <div style={{ marginLeft: "auto", display: "flex", gap: 4, flexShrink: 0 }}>
            <button
              onClick={() => setDock((d) => (d === "right" ? "left" : "right"))}
              title={dock === "right" ? "Move to left side" : "Move to right side"}
              style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted-foreground)", padding: 5, display: "flex" }}
            >
              {dock === "right" ? <PanelLeftClose size={15} /> : <PanelRightClose size={15} />}
            </button>
            <button
              onClick={() => setOpen(false)}
              title="Minimize"
              style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted-foreground)", padding: 5, display: "flex" }}
            >
              <Minus size={15} />
            </button>
            <button
              onClick={() => setOpen(false)}
              title="Close"
              style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted-foreground)", padding: 5, display: "flex" }}
            >
              <X size={15} />
            </button>
          </div>
        </div>

        {/* Messages */}
        <div style={{ flex: 1, overflowY: "auto", padding: "16px", display: "flex", flexDirection: "column", gap: 14 }}>
          {messages.map((msg) => (
            <div
              key={msg.id}
              style={{
                display: "flex",
                gap: 8,
                flexDirection: msg.role === "user" ? "row-reverse" : "row",
                alignItems: "flex-start",
              }}
            >
              <div
                style={{
                  width: 24,
                  height: 24,
                  borderRadius: "50%",
                  flexShrink: 0,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  background: msg.role === "assistant"
                    ? "linear-gradient(135deg, var(--primary), #7B61FF)"
                    : "var(--muted)",
                  border: msg.role === "user" ? "1px solid var(--border)" : "none",
                }}
              >
                {msg.role === "assistant"
                  ? <Bot size={12} style={{ color: "#fff" }} />
                  : <User size={12} style={{ color: "var(--muted-foreground)" }} />
                }
              </div>

              <div style={{ maxWidth: "80%", display: "flex", flexDirection: "column", gap: 6 }}>
                <div
                  style={{
                    padding: "9px 12px",
                    borderRadius: msg.role === "user" ? "10px 3px 10px 10px" : "3px 10px 10px 10px",
                    background: msg.role === "user" ? "var(--primary)" : "var(--muted)",
                    fontSize: 12.5,
                    color: msg.role === "user" ? "#fff" : "var(--foreground)",
                    lineHeight: 1.55,
                    whiteSpace: "pre-wrap",
                  }}
                >
                  {msg.text}
                </div>

                {msg.products && msg.products.length > 0 && (
                  <div className="flex gap-2" style={{ flexWrap: "nowrap", overflowX: "auto", paddingBottom: 2 }}>
                    {msg.products.map((p) => {
                      const added = isInCart(p.id);
                      return (
                        <div
                          key={p.id}
                          style={{
                            background: "var(--surface)",
                            border: "1px solid var(--border)",
                            borderRadius: 8,
                            padding: 8,
                            minWidth: 128,
                            flexShrink: 0,
                          }}
                        >
                          <img
                            src={p.image}
                            alt={p.name}
                            style={{ width: "100%", height: 72, objectFit: "cover", borderRadius: 5, marginBottom: 6 }}
                          />
                          <p style={{ fontSize: 10.5, fontWeight: 600, color: "var(--foreground)", marginBottom: 4, lineHeight: 1.3 }}>{p.name}</p>
                          <div className="flex items-center justify-between mb-2">
                            <span style={{ fontSize: 11, fontWeight: 700, color: "var(--primary)" }}>{formatEUR(p.price)}</span>
                            <span style={{ fontSize: 8.5, color: "var(--primary)", background: "rgba(var(--primary-rgb),0.1)", padding: "1px 5px", borderRadius: 10 }}>
                              {p.aiScore}%
                            </span>
                          </div>
                          <button
                            onClick={() => addItem(p)}
                            disabled={added}
                            style={{
                              width: "100%",
                              padding: "5px",
                              background: added ? "#22C55E" : "var(--primary)",
                              border: "none",
                              borderRadius: 50,
                              color: "#fff",
                              fontSize: 9.5,
                              fontWeight: 600,
                              cursor: added ? "default" : "pointer",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              gap: 3,
                            }}
                          >
                            {added ? <><Check size={9} /> Added</> : <><ShoppingCart size={9} /> Add</>}
                          </button>
                        </div>
                      );
                    })}
                  </div>
                )}

                <span style={{ fontSize: 9, color: "var(--muted-foreground)" }}>{msg.timestamp}</span>
              </div>
            </div>
          ))}

          {typing && (
            <div className="flex gap-2 items-center">
              <div
                style={{
                  width: 24,
                  height: 24,
                  borderRadius: "50%",
                  background: "linear-gradient(135deg, var(--primary), #7B61FF)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                }}
              >
                <Bot size={12} style={{ color: "#fff" }} />
              </div>
              <div
                style={{
                  background: "var(--muted)",
                  borderRadius: "3px 10px 10px 10px",
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
        <div style={{ padding: "6px 14px", borderTop: "1px solid var(--border)", display: "flex", gap: 6, flexWrap: "nowrap", overflowX: "auto" }}>
          {suggestions.map((s) => (
            <button
              key={s}
              onClick={() => send(s)}
              disabled={typing}
              style={{
                padding: "4px 10px",
                borderRadius: 20,
                border: "1px solid var(--border)",
                background: "transparent",
                color: "var(--muted-foreground)",
                fontSize: 10.5,
                cursor: typing ? "default" : "pointer",
                whiteSpace: "nowrap",
                flexShrink: 0,
              }}
            >
              {s}
            </button>
          ))}
        </div>

        {/* Input */}
        <div style={{ padding: "10px 14px 12px", borderTop: "1px solid var(--border)", display: "flex", gap: 8, flexShrink: 0 }}>
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
                borderRadius: 5,
                display: "flex",
              }}
            >
              {listening ? <MicOff size={13} /> : <Mic size={13} />}
            </button>
          </div>
          <button
            onClick={() => send(input)}
            disabled={typing}
            style={{
              padding: "9px 14px",
              background: "var(--primary)",
              border: "none",
              borderRadius: 50,
              color: "#fff",
              cursor: typing ? "default" : "pointer",
              opacity: typing ? 0.6 : 1,
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
