import { useState, useRef, useEffect, useCallback, Fragment } from "react";
import {
  Send, Mic, MicOff, Sparkles, ShoppingCart, X,
  Maximize2, Minimize2, Check, SquarePen, History, ChevronLeft, Plus, Trash2,
  SlidersHorizontal,
} from "lucide-react";
import { useCart } from "../cart/CartContext";
import { useAuth } from "../auth/AuthContext";
import {
  askAssistant, askAssistantStream, deleteConversation,
  fetchChatHistory, fetchConversations, resolveHistoryProducts,
} from "../api/api";
import { PreferencesPanel } from "./PreferencesPanel";
import { AuthModal } from "./AuthModal";
import { ColorDots } from "./ColorDots";
import { formatEUR } from "../lib/format";
import { useSpeechRecognition } from "../lib/useSpeechRecognition";
import type { ChatMessage, Product } from "../types";

type DockSide = "left" | "right";
type ChatSize = "compact" | "expanded";

const DOCK_KEY = "oneshop-chat-dock";
const CONV_KEY = "oneshop-chat-conv-id";

function loadConvId(): string {
  return localStorage.getItem(CONV_KEY) ?? "";
}
function saveConvId(id: string): void {
  localStorage.setItem(CONV_KEY, id);
}
function generateConvId(): string {
  const id =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? `conv-${crypto.randomUUID()}`
      : `conv-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  saveConvId(id);
  return id;
}

// ─── Conversation list entries ─────────────────────────────────────────────────
// Served by the backend (title + updated_at per thread), never cached in
// localStorage: names must not leak to the next user on a shared device.
interface ConvMeta {
  id: string;
  preview: string; // conversation title (first user message, truncated server-side)
  updatedAt: number;
}

function relativeTime(ts: number): string {
  if (!ts) return "";
  const diff = Date.now() - ts;
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days === 1) return "Yesterday";
  if (days < 7) return `${days}d ago`;
  return new Date(ts).toLocaleDateString("de-DE", { day: "2-digit", month: "short" });
}

const WELCOME: ChatMessage = {
  id: 1,
  role: "assistant",
  text: "Hi — I'm your OneShop AI assistant. Ask about phones, tablets, laptops, wearables, audio, accessories, or plans — tell me your budget and what matters to you, and I'll find the best match.",
  timestamp: new Date().toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }),
};

const CHIPS = ["Phone between €500-800", "Best camera phone", "Noise-cancelling audio", "Show me deals"];

// ─── History loading skeleton ──────────────────────────────────────────────────
function HistorySkeleton() {
  const bar = (w: string, delay: number) => (
    <div
      style={{
        width: w,
        height: 13,
        background: "var(--muted)",
        borderRadius: 6,
        animation: `skeleton-pulse 1.4s ${delay}s ease-in-out infinite`,
      }}
    />
  );
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20, paddingTop: 4 }}>
      {/* Simulated assistant turn */}
      <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 6 }}>
        {bar("72%", 0)}
        {bar("54%", 0.08)}
      </div>
      {/* Simulated user turn */}
      <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 6 }}>
        <div
          style={{
            width: "46%",
            height: 38,
            background: "var(--muted)",
            borderRadius: "16px 16px 3px 16px",
            animation: "skeleton-pulse 1.4s 0.16s ease-in-out infinite",
          }}
        />
      </div>
      {/* Simulated assistant turn */}
      <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 6 }}>
        {bar("80%", 0.24)}
        {bar("62%", 0.32)}
        {bar("40%", 0.40)}
      </div>
    </div>
  );
}

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
  inCart,
}: {
  product: Product;
  expanded: boolean;
  onAdd: () => void;
  inCart: boolean;
}) {
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
          style={{ width: "100%", height: "100%", objectFit: "contain", objectPosition: "center", display: "block" }}
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

        {/* Rating + key specs */}
        {(product.reviews > 0 || product.specs.length > 0) && (
          <p style={{ fontSize: 9.5, color: "var(--muted-foreground)", marginBottom: 4, lineHeight: 1.4 }}>
            {product.reviews > 0 && <>★ {product.stars} ({product.reviews.toLocaleString()})</>}
            {product.reviews > 0 && product.specs.length > 0 && " · "}
            {product.specs.slice(0, 2).join(" · ")}
          </p>
        )}

        {/* Available colors */}
        {product.colors.length > 0 && (
          <div style={{ marginBottom: 6 }}>
            <ColorDots colors={product.colors} size={11} max={5} />
          </div>
        )}

        {/* Price */}
        <div style={{ marginBottom: 9 }}>
          <span style={{ fontSize: expanded ? 14 : 13, fontWeight: 700, color: "var(--foreground)" }}>
            {formatEUR(product.price)}
          </span>
          {product.originalPrice > 0 && (
            <span
              style={{
                fontSize: 9.5,
                color: "var(--muted-foreground)",
                textDecoration: "line-through",
                marginLeft: 5,
              }}
            >
              {formatEUR(product.originalPrice)}
            </span>
          )}
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

// ─── Sign-in gate ──────────────────────────────────────────────────────────────
function SignInGate({ onSignIn }: { onSignIn: () => void }) {
  return (
    <div
      style={{
        flex: 1, display: "flex", flexDirection: "column", alignItems: "center",
        justifyContent: "center", gap: 14, padding: "32px 28px", textAlign: "center",
      }}
    >
      <div
        style={{
          width: 52, height: 52, borderRadius: "50%",
          background: "linear-gradient(145deg, var(--primary) 0%, #7C3AED 100%)",
          display: "flex", alignItems: "center", justifyContent: "center",
        }}
      >
        <Sparkles size={22} color="#fff" />
      </div>
      <p style={{ fontSize: 14, fontWeight: 700, color: "var(--foreground)", margin: 0 }}>
        Sign in to chat
      </p>
      <p style={{ fontSize: 12.5, color: "var(--muted-foreground)", lineHeight: 1.6, margin: 0, maxWidth: 280 }}>
        Your conversations, budget, and preferences are saved to your account, so the
        assistant remembers you on every device.
      </p>
      <button
        onClick={onSignIn}
        style={{
          marginTop: 4, padding: "10px 26px", borderRadius: 12, border: "none",
          background: "var(--primary)", color: "#fff", fontSize: 13, fontWeight: 600,
          cursor: "pointer", transition: "opacity 0.15s",
        }}
        onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.opacity = "0.88"; }}
        onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.opacity = "1"; }}
      >
        Sign in or create account
      </button>
    </div>
  );
}

// ─── Main component ────────────────────────────────────────────────────────────
export function FloatingChat() {
  const [open, setOpen] = useState(false);
  const [size, setSize] = useState<ChatSize>("compact");
  const [dock, setDock] = useState<DockSide>(() => {
    if (typeof window === "undefined") return "right";
    return (localStorage.getItem(DOCK_KEY) as DockSide) === "left" ? "left" : "right";
  });
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [typing, setTyping] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyCount, setHistoryCount] = useState(0); // how many messages came from history
  const [conversationId, setConversationId] = useState<string>(loadConvId);
  const [view, setView] = useState<"chat" | "list" | "prefs">("chat");
  const [convMetas, setConvMetas] = useState<ConvMeta[]>([]);
  // Ref so loadHistory / send can always read the latest conv ID without being in deps
  const convIdRef = useRef(conversationId);

  const { user } = useAuth();
  const [authOpen, setAuthOpen] = useState(false);

  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const historyLoadedRef = useRef(false); // true once history fetch completes for the current session

  // Keep ref in sync with state so callbacks always see the latest value
  useEffect(() => { convIdRef.current = conversationId; }, [conversationId]);
  const { addItem, isInCart } = useCart();

  const { listening, supported: micSupported, toggleListening } = useSpeechRecognition((t) =>
    setInput((prev) => (prev ? `${prev} ${t}` : t)),
  );

  useEffect(() => { localStorage.setItem(DOCK_KEY, dock); }, [dock]);

  const refreshConversations = useCallback(async (): Promise<ConvMeta[]> => {
    try {
      const list = await fetchConversations();
      const metas = list.map((c) => ({ id: c.id, preview: c.title, updatedAt: c.updatedAt }));
      setConvMetas(metas);
      return metas;
    } catch {
      return [];
    }
  }, []);

  // Refresh the thread list from the backend whenever the list panel opens.
  useEffect(() => {
    if (view !== "list" || !user) return;
    refreshConversations();
  }, [view, user, refreshConversations]);

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

  const loadHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      const { conversationId: returnedId, history } = await fetchChatHistory(convIdRef.current || undefined);

      // If the backend minted a conversation ID (no stored one), remember it
      if (returnedId && returnedId !== convIdRef.current) {
        setConversationId(returnedId);
        saveConvId(returnedId);
        convIdRef.current = returnedId;
      }

      if (history.length === 0) {
        setMessages([WELCOME]);
        setHistoryCount(0);
        return;
      }

      // Restore product cards from persisted recommendations (single catalog fetch)
      const productsByIndex = await resolveHistoryProducts(history);

      setMessages(
        history.map((msg, i) => ({
          id: i + 1,
          role: msg.role as "user" | "assistant",
          text: msg.content,
          timestamp: "", // backend doesn't persist timestamps
          products: productsByIndex.get(i),
        })),
      );
      setHistoryCount(history.length);
    } catch {
      setMessages([WELCOME]);
      setHistoryCount(0);
    } finally {
      setHistoryLoading(false);
      historyLoadedRef.current = true;
    }
  }, []);

  const startNewChat = useCallback(() => {
    const newId = generateConvId();
    setConversationId(newId);
    convIdRef.current = newId;
    setMessages([WELCOME]);
    setHistoryCount(0);
    historyLoadedRef.current = true;
    setView("chat");
  }, []);

  const switchToConversation = useCallback((id: string) => {
    setConversationId(id);
    saveConvId(id);
    convIdRef.current = id;
    setMessages([]);
    setHistoryCount(0);
    historyLoadedRef.current = false;
    setView("chat");
    loadHistory();
  }, [loadHistory]);

  // When the panel opens for the first time, default to the conversations list if the user
  // has prior history — mirrors ChatGPT/Claude where you land on the conversation picker.
  // Otherwise go straight to the chat (WELCOME message path).
  useEffect(() => {
    if (open && user && !historyLoadedRef.current) {
      historyLoadedRef.current = true; // don't auto-load any single thread yet
      refreshConversations().then((metas) => {
        if (metas.length > 0) {
          setView("list");
        } else {
          startNewChat();
        }
      });
    }
  }, [open, user, refreshConversations, startNewChat]);

  // Reset all per-identity state when the session changes (login/logout), so
  // nothing from the previous user — thread list, active thread, messages —
  // is visible to the next one on this device.
  useEffect(() => {
    const handler = () => {
      setMessages([]);
      setHistoryCount(0);
      setConvMetas([]);
      setConversationId("");
      convIdRef.current = "";
      saveConvId("");
      setView("chat");
        historyLoadedRef.current = false; // the open-panel effect re-initializes for the new identity
    };
    window.addEventListener("oneshop-session-changed", handler);
    return () => window.removeEventListener("oneshop-session-changed", handler);
  }, []);

  // No auth gate here — guests can add to cart. Cart requires auth at checkout, not add.
  const handleAdd = useCallback(
    (p: Product) => { addItem(p); },
    [addItem],
  );

  const send = (text: string) => {
    if (!text.trim() || typing) return;
    const now = () => new Date().toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
    setMessages((prev) => [...prev, { id: Date.now(), role: "user", text, timestamp: now() }]);
    setInput("");
    setTyping(true);

    // If no conversation yet, generate one now so the first message starts a thread
    if (!convIdRef.current) {
      const newId = generateConvId();
      setConversationId(newId);
      convIdRef.current = newId;
    }

    const assistantId = Date.now() + 1;
    let streamStarted = false;
    const appendToken = (delta: string) => {
      if (!streamStarted) {
        streamStarted = true;
        setTyping(false);
        setMessages((prev) => [
          ...prev,
          { id: assistantId, role: "assistant", text: delta, timestamp: now() },
        ]);
        return;
      }
      setMessages((prev) =>
        prev.map((m) => (m.id === assistantId ? { ...m, text: m.text + delta } : m)),
      );
    };

    const applyResult = ({ reply, products, conversationId: returnedId }: {
      reply: string; products?: Product[]; conversationId: string;
    }) => {
      // Backend echoes back the conversation_id (may have generated it server-side)
      if (returnedId && returnedId !== convIdRef.current) {
        setConversationId(returnedId);
        saveConvId(returnedId);
        convIdRef.current = returnedId;
      }
      setMessages((prev) =>
        streamStarted
          ? prev.map((m) => (m.id === assistantId ? { ...m, text: reply, products } : m))
          : [...prev, { id: assistantId, role: "assistant", text: reply, products, timestamp: now() }],
      );
    };

    const showError = () =>
      setMessages((prev) => [
        ...prev.filter((m) => m.id !== assistantId),
        {
          id: assistantId,
          role: "assistant" as const,
          text: "Sorry, I couldn't reach the service right now. Please try again.",
          timestamp: now(),
        },
      ]);

    (async () => {
      try {
        applyResult(await askAssistantStream(text, convIdRef.current, appendToken));
      } catch {
        if (streamStarted) {
          showError();
        } else {
          // Streaming never started (proxy/SSE issue) — safe to retry non-streaming.
          try {
            applyResult(await askAssistant(text, convIdRef.current));
          } catch {
            showError();
          }
        }
      } finally {
        setTyping(false);
      }
    })();
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
          {view !== "chat" ? (
            /* List / preferences view header */
            <>
              <button
                onClick={() => {
                  setView("chat");
                  if (messages.length === 0) {
                    if (convIdRef.current) {
                      historyLoadedRef.current = false;
                      loadHistory();
                    } else {
                      setMessages([WELCOME]);
                      historyLoadedRef.current = true;
                    }
                  }
                }}
                style={{
                  background: "none", border: "none", cursor: "pointer",
                  display: "flex", alignItems: "center", gap: 4,
                  color: "var(--muted-foreground)", padding: "4px 2px", borderRadius: 6,
                }}
              >
                <ChevronLeft size={16} />
              </button>
              <span style={{ flex: 1, fontSize: 14, fontWeight: 700, color: "var(--foreground)" }}>
                {view === "list" ? "Conversations" : "Your preferences"}
              </span>
              <IconBtn
                danger
                title="Close"
                onClick={() => { setOpen(false); setSize("compact"); setView("chat"); }}
              >
                <X size={14} />
              </IconBtn>
            </>
          ) : (
            /* Chat view header */
            <>
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

              {/* Actions */}
              <div style={{ display: "flex", gap: 1 }}>
                {user && (
                  <>
                    <IconBtn title="New chat" onClick={startNewChat}>
                      <SquarePen size={14} />
                    </IconBtn>
                    <IconBtn title="History" onClick={() => setView("list")}>
                      <History size={14} />
                    </IconBtn>
                    <IconBtn title="Preferences the assistant learned" onClick={() => setView("prefs")}>
                      <SlidersHorizontal size={14} />
                    </IconBtn>
                  </>
                )}
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
            </>
          )}
        </div>

        {/* ── Sign-in gate (chat requires an account) ────────────────────────── */}
        {!user && <SignInGate onSignIn={() => setAuthOpen(true)} />}

        {/* ── Conversation list ──────────────────────────────────────────────── */}
        {user && view === "list" && (
          <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
            {/* New Chat button */}
            <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--border)" }}>
              <button
                onClick={startNewChat}
                style={{
                  width: "100%", padding: "10px 16px",
                  background: "var(--primary)", border: "none", borderRadius: 12,
                  color: "#fff", fontSize: 13, fontWeight: 600, cursor: "pointer",
                  display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
                  transition: "opacity 0.15s",
                }}
                onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.opacity = "0.88"; }}
                onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.opacity = "1"; }}
              >
                <Plus size={14} /> New Chat
              </button>
            </div>

            {/* List */}
            <div style={{ flex: 1, overflowY: "auto", scrollbarWidth: "none", msOverflowStyle: "none" }}>
              {convMetas.length === 0 ? (
                <div style={{ padding: "48px 24px", textAlign: "center", color: "var(--muted-foreground)", fontSize: 13 }}>
                  No past conversations yet.<br />
                  <span style={{ fontSize: 11, marginTop: 4, display: "block" }}>Start chatting to see your history here.</span>
                </div>
              ) : (
                convMetas.map((meta) => (
                  <ConvItem
                    key={meta.id}
                    meta={meta}
                    active={meta.id === conversationId}
                    onSelect={() => switchToConversation(meta.id)}
                    onDelete={() => {
                      setConvMetas((metas) => metas.filter((m) => m.id !== meta.id));
                      deleteConversation(meta.id).catch(() => {});
                      if (meta.id === conversationId) startNewChat();
                    }}
                  />
                ))
              )}
            </div>
          </div>
        )}

        {/* ── Preferences ────────────────────────────────────────────────────── */}
        {user && view === "prefs" && <PreferencesPanel />}

        {/* ── Messages ───────────────────────────────────────────────────────── */}
        {user && view === "chat" && <div
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
          {historyLoading ? (
            <HistorySkeleton />
          ) : (
            <>
              {/* "Earlier" header — only when history was restored */}
              {historyCount > 0 && (
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    marginBottom: 2,
                  }}
                >
                  <div style={{ flex: 1, height: 1, background: "var(--border)" }} />
                  <span
                    style={{
                      fontSize: 10,
                      color: "var(--muted-foreground)",
                      fontWeight: 500,
                      whiteSpace: "nowrap",
                    }}
                  >
                    Earlier
                  </span>
                  <div style={{ flex: 1, height: 1, background: "var(--border)" }} />
                </div>
              )}

              {messages.map((msg, i) => (
                <Fragment key={msg.id}>
                  {/* "New" divider between historical and freshly sent messages */}
                  {historyCount > 0 && i === historyCount && (
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                        margin: "2px 0",
                      }}
                    >
                      <div style={{ flex: 1, height: 1, background: "var(--border)" }} />
                      <span
                        style={{
                          fontSize: 10,
                          color: "var(--muted-foreground)",
                          fontWeight: 500,
                          whiteSpace: "nowrap",
                        }}
                      >
                        New
                      </span>
                      <div style={{ flex: 1, height: 1, background: "var(--border)" }} />
                    </div>
                  )}

                  <div
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
                            inCart={isInCart(p.id)}
                          />
                        ))}
                      </div>
                    )}

                    {/* Timestamp — historical messages have no timestamp stored */}
                    {msg.timestamp && (
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
                    )}
                  </div>
                </Fragment>
              ))}
            </>
          )}

          {!historyLoading && typing && <TypingIndicator />}
          <div ref={bottomRef} />
        </div>}

        {/* ── Suggestion chips ───────────────────────────────────────────────── */}
        {user && view === "chat" && <div
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
            <ChipBtn key={chip} label={chip} disabled={typing || historyLoading} onClick={() => send(chip)} />
          ))}
        </div>}

        {/* ── Input area ─────────────────────────────────────────────────────── */}
        {user && view === "chat" && <div style={{ padding: "10px 14px 16px", flexShrink: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{ flex: 1, position: "relative" }}>
              <input
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && send(input)}
                placeholder={historyLoading ? "Loading your conversation…" : "Ask about products, plans, bundles…"}
                disabled={historyLoading}
                style={{
                  width: "100%",
                  padding: micSupported ? "10px 40px 10px 14px" : "10px 14px",
                  background: "var(--input-background)",
                  border: "1.5px solid var(--border)",
                  borderRadius: 12,
                  fontSize: 13,
                  color: "var(--foreground)",
                  outline: "none",
                  opacity: historyLoading ? 0.5 : 1,
                  transition: "border-color 0.15s, box-shadow 0.15s, opacity 0.15s",
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
              disabled={typing || !input.trim() || historyLoading}
              style={{
                width: 40,
                height: 40,
                flexShrink: 0,
                border: "none",
                borderRadius: "50%",
                cursor: typing || !input.trim() || historyLoading ? "default" : "pointer",
                background:
                  typing || !input.trim() || historyLoading
                    ? "var(--muted)"
                    : "linear-gradient(145deg, var(--primary) 0%, #7C3AED 100%)",
                color: typing || !input.trim() || historyLoading ? "var(--muted-foreground)" : "#fff",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                boxShadow:
                  typing || !input.trim() || historyLoading
                    ? "none"
                    : "0 2px 8px rgba(var(--primary-rgb),.4)",
                transition: "background 0.18s, box-shadow 0.18s, color 0.18s",
              }}
            >
              <Send size={15} />
            </button>
          </div>
        </div>}
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
        }
        @keyframes skeleton-pulse {
          0%, 100% { opacity: 0.4; }
          50%       { opacity: 1; }
        }
        /* Hide webkit scrollbar in messages and chip rows */
        div::-webkit-scrollbar { display: none; }
      `}</style>
    </>
  );
}

// ─── Conversation list item ────────────────────────────────────────────────────
function ConvItem({
  meta,
  active,
  onSelect,
  onDelete,
}: {
  meta: ConvMeta;
  active: boolean;
  onSelect: () => void;
  onDelete: () => void;
}) {
  const [hov, setHov] = useState(false);
  return (
    <div
      onClick={onSelect}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        padding: "12px 16px",
        borderBottom: "1px solid var(--border)",
        cursor: "pointer",
        background: active
          ? "rgba(var(--primary-rgb),0.07)"
          : hov
          ? "var(--muted)"
          : "transparent",
        display: "flex",
        alignItems: "center",
        gap: 10,
        transition: "background 0.12s",
      }}
    >
      {/* Message icon */}
      <div
        style={{
          width: 32,
          height: 32,
          borderRadius: 8,
          background: active ? "rgba(var(--primary-rgb),0.15)" : "var(--muted)",
          flexShrink: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <Sparkles size={13} style={{ color: active ? "var(--primary)" : "var(--muted-foreground)" }} />
      </div>

      {/* Preview text + time */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <p
          style={{
            fontSize: 12.5,
            fontWeight: active ? 600 : 500,
            color: "var(--foreground)",
            overflow: "hidden",
            whiteSpace: "nowrap",
            textOverflow: "ellipsis",
            marginBottom: 2,
          }}
        >
          {meta.preview || "Previous conversation"}
        </p>
        {meta.updatedAt > 0 && (
          <p style={{ fontSize: 10.5, color: "var(--muted-foreground)" }}>
            {relativeTime(meta.updatedAt)}
          </p>
        )}
      </div>

      {/* Delete button — shown on hover */}
      {hov && (
        <button
          onClick={(e) => { e.stopPropagation(); onDelete(); }}
          style={{
            background: "none", border: "none", cursor: "pointer",
            color: "var(--muted-foreground)", padding: 4, borderRadius: 6,
            display: "flex", alignItems: "center", flexShrink: 0,
            transition: "color 0.12s",
          }}
          onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.color = "#EF4444"; }}
          onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.color = "var(--muted-foreground)"; }}
          title="Delete conversation"
        >
          <Trash2 size={13} />
        </button>
      )}
    </div>
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
