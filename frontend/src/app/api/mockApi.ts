import type {
  Product, AppNotification, LiveActivity, RegisterPayload, LoginPayload, AuthUser,
  ShippingDetails, PaymentDetails,
} from "../types";
import { getSessionId, setSessionId, getAuthToken, setAuthToken, clearSessionId } from "./session";

/**
 * Real API client. Kept the filename/exports from the original Figma mock so no
 * component needed to change - only what's inside these functions did. Every
 * function here now calls the FastAPI backend (see PROJECT_OVERVIEW.md's
 * architecture section) instead of returning fabricated data.
 */
const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

// --- raw backend shapes (see backend/app/contracts/models.py - the source of truth) ---
interface BackendProduct {
  id: string;
  type: "phone" | "plan" | "accessory" | "bundle";
  name: string;
  brand: string;
  description: string;
  price_monthly: number;
  price_onetime: number;
  category: string;
  features: string[];
  compatible_plans: string[];
  stock: number;
  in_stock: boolean;
  image_url: string;
}

interface BackendRecommendation {
  product_id: string;
  rank: number;
  score: number;
  why: string;
  bundle: string[];
}

interface BackendChatResponse {
  reply_text: string;
  recommendations: BackendRecommendation[];
  nba: string[];
  conversation_id: string;
}

interface BackendCheckoutResult {
  order_id: string;
  onetime_total: number;
  monthly_total: number;
  free_shipping: boolean;
  status: string;
}

async function fetchRawCatalog(): Promise<BackendProduct[]> {
  const res = await fetch(`${BASE}/catalog`);
  if (!res.ok) throw new Error("Could not load the catalog. Please try again.");
  return res.json();
}

function titleCase(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function placeholderImage(name: string): string {
  // Fallback only - used if a product is missing image_url (e.g. added to the
  // catalog without one). A clearly-a-placeholder image, not a fabricated
  // "real photo" of a device we don't have art for.
  return `https://placehold.co/400x400/1a1a2e/ffffff?text=${encodeURIComponent(name)}`;
}

function clampScore(n: number): number {
  return Math.max(0, Math.min(99, Math.round(n)));
}

/** A disclosed, deterministic heuristic for the plain catalog browse (no
 * personalization context there - it's a flat GET /catalog, not a
 * recommendation). More real features + being in stock nudges it up. This is
 * NOT a fabricated trust signal: it's a transparent function of real fields. */
function heuristicScore(p: BackendProduct): number {
  return clampScore(55 + p.features.length * 6 + (p.in_stock ? 10 : 0));
}

/** Adapt a real catalog product into the UI's display shape. When `why`/`score`
 * come from an actual /chat recommendation, they're the genuine grounded
 * explanation and ranking score - not invented. Star ratings/review counts have
 * no real data source anywhere in this system, so they're honestly 0 rather
 * than fabricated social proof. */
function adaptProduct(p: BackendProduct, score?: number, why?: string): Product {
  const price = p.price_onetime > 0 ? p.price_onetime : p.price_monthly;
  const monthlyPrice = p.price_onetime > 0 ? p.price_monthly : 0;

  const reasons = why
    ? [why]
    : [
        p.in_stock ? `${p.stock} in stock` : "Currently unavailable",
        p.features.length ? `Features: ${p.features.map(titleCase).join(", ")}` : "",
        p.price_monthly > 0 ? `€${p.price_monthly}/mo` : price > 0 ? `€${price} one-time` : "",
      ].filter(Boolean);

  return {
    id: p.id,
    name: p.name,
    category: titleCase(p.category || p.type),
    price,
    monthlyPrice,
    image: p.image_url || placeholderImage(p.name),
    badge: !p.in_stock ? "Out of Stock" : why ? "AI Pick" : "In Stock",
    badgeColor: !p.in_stock ? "#FF3B30" : why ? "var(--primary)" : "#00C2A8",
    aiScore: score !== undefined ? clampScore(score) : heuristicScore(p),
    stars: 0,     // no review data exists yet - honest zero, not a fabricated rating
    reviews: 0,
    tags: p.features.map(titleCase),
    reasons,
    inStock: p.in_stock,
    trend: p.in_stock ? `${p.stock} in stock` : "Currently unavailable",
  };
}

export function getProducts(): Promise<Product[]> {
  return fetchRawCatalog().then((raw) => raw.map((p) => adaptProduct(p)));
}

export async function getBundleSuggestions(excludeIds: string[]): Promise<Product[]> {
  const res = await fetch(`${BASE}/cart/suggestions?session_id=${getSessionId()}&limit=3`);
  if (!res.ok) return [];
  const raw: BackendProduct[] = await res.json();
  return raw.filter((p) => !excludeIds.includes(p.id)).map((p) => adaptProduct(p));
}

// No backend notification system exists - honestly empty rather than fabricated.
export function getNotifications(): Promise<AppNotification[]> {
  return Promise.resolve([]);
}

export async function getLiveActivity(productId: string): Promise<LiveActivity> {
  // No real viewer telemetry exists anywhere in this system - 0 rather than a
  // fabricated "N people viewing" urgency claim. Stock IS real, from the catalog.
  const res = await fetch(`${BASE}/catalog/${productId}`);
  if (!res.ok) return { viewers: 0, stockLeft: 0 };
  const p: BackendProduct = await res.json();
  return { viewers: 0, stockLeft: p.stock };
}

export interface HistoryMessage {
  role: "user" | "assistant";
  content: string;
  recommendations: BackendRecommendation[];
}

interface AssistantReply {
  reply: string;
  products?: Product[];
  conversationId: string;
}

export async function askAssistant(message: string, conversationId: string): Promise<AssistantReply> {
  const res = await fetch(`${BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: getSessionId(), message, conversation_id: conversationId || undefined }),
  });
  if (!res.ok) throw new Error("Sorry, I couldn't reach the recommendation service. Please try again.");
  const data: BackendChatResponse = await res.json();

  let products: Product[] | undefined;
  if (data.recommendations.length) {
    const catalog = await fetchRawCatalog();
    const byId = new Map(catalog.map((p) => [p.id, p]));
    products = data.recommendations
      .map((rec) => {
        const raw = byId.get(rec.product_id);
        // The backend's guardrail already forbids this, but stay defensive.
        return raw ? adaptProduct(raw, rec.score * 10, rec.why) : null;
      })
      .filter((p): p is Product => p !== null);
  }

  // Surface next-best-action nudges in the same reply bubble (no new UI element).
  const reply = data.nba.length ? `${data.reply_text}\n\n${data.nba.join("\n")}` : data.reply_text;
  return { reply, products, conversationId: data.conversation_id };
}

/** Restore product cards for all assistant messages in a history list.
 *  Fetches the catalog once and resolves all recommendations in one pass. */
export async function resolveHistoryProducts(
  history: HistoryMessage[],
): Promise<Map<number, Product[]>> {
  const hasAnyRecs = history.some((m) => m.role === "assistant" && m.recommendations?.length > 0);
  if (!hasAnyRecs) return new Map();

  const catalog = await fetchRawCatalog();
  const byId = new Map(catalog.map((p) => [p.id, p]));
  const result = new Map<number, Product[]>();

  history.forEach((msg, i) => {
    if (msg.role !== "assistant" || !msg.recommendations?.length) return;
    const products = msg.recommendations
      .map((rec) => {
        const raw = byId.get(rec.product_id);
        return raw ? adaptProduct(raw, rec.score * 10, rec.why) : null;
      })
      .filter((p): p is Product => p !== null);
    if (products.length) result.set(i, products);
  });

  return result;
}

export interface OrderResult {
  orderNumber: string;
  estimatedDelivery: string;
}

export async function createOrder(
  _shipping: ShippingDetails,
  _payment: PaymentDetails,
  _items: unknown,
): Promise<OrderResult> {
  // Checkout is a mock confirmation (no real payment processor) - a deliberate,
  // disclosed 24h-POC cut. See docs/DEMO_RUNBOOK.md.
  const res = await fetch(`${BASE}/cart/checkout`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: getSessionId() }),
  });
  if (!res.ok) throw new Error("Could not place the order. Please try again.");
  const data: BackendCheckoutResult = await res.json();
  const eta = new Date(Date.now() + 3 * 24 * 60 * 60 * 1000); // no logistics system - a generic delivery estimate
  return {
    orderNumber: data.order_id,
    estimatedDelivery: eta.toLocaleDateString("de-DE", { day: "2-digit", month: "short" }),
  };
}

// --- auth ---
// Both attach the current (guest) session_id so its cart/history merge into the
// account on the backend; the returned user_id then becomes our session_id.
export async function registerUser(payload: RegisterPayload): Promise<AuthUser> {
  const res = await fetch(`${BASE}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...payload, session_id: getSessionId() }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => null);
    throw new Error(err?.detail || "Could not create your account. Please try again.");
  }
  const data = await res.json();
  setSessionId(data.user_id);
  setAuthToken(data.token);
  return { userId: data.user_id, email: data.email, name: data.name, token: data.token };
}

export async function loginUser(payload: LoginPayload): Promise<AuthUser> {
  const res = await fetch(`${BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...payload, session_id: getSessionId() }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => null);
    throw new Error(err?.detail || "Invalid email or password.");
  }
  const data = await res.json();
  setSessionId(data.user_id);
  setAuthToken(data.token);
  return { userId: data.user_id, email: data.email, name: data.name, token: data.token };
}

export function logoutUser(): void {
  setAuthToken(null);
  // Reset to a fresh guest session so the logged-out user's cart is not visible
  // to whoever opens the browser next. Re-login will restore their server-side cart.
  clearSessionId();
}

export async function fetchConversations(): Promise<string[]> {
  const res = await fetch(`${BASE}/chat/conversations?session_id=${getSessionId()}`);
  if (!res.ok) return [];
  const data: { session_id: string; conversation_ids: string[] } = await res.json();
  return data.conversation_ids ?? [];
}

export async function fetchChatHistory(conversationId?: string): Promise<{
  conversationId: string;
  history: HistoryMessage[];
}> {
  const params = new URLSearchParams({ session_id: getSessionId() });
  if (conversationId) params.set("conversation_id", conversationId);
  const res = await fetch(`${BASE}/chat/history?${params}`);
  if (!res.ok) return { conversationId: conversationId ?? "", history: [] };
  const data: { conversation_id: string; history: HistoryMessage[] } = await res.json();
  return { conversationId: data.conversation_id ?? "", history: data.history ?? [] };
}

export interface ChatHistoryMessage {
  role: "user" | "assistant" | "system";
  content: string;
  recommendations: BackendRecommendation[];
}

// Persisted conversation for the current session/user. Sends the auth token so
// the backend authorizes reads of a logged-in account's private history.
export async function getChatHistory(conversationId = ""): Promise<ChatHistoryMessage[]> {
  const token = getAuthToken();
  const q = conversationId ? `&conversation_id=${encodeURIComponent(conversationId)}` : "";
  const res = await fetch(`${BASE}/chat/history?session_id=${getSessionId()}${q}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) return [];
  const data = await res.json();
  return data.history || [];
}

// Restores the logged-in user on page load from a stored token, if any.
export async function getCurrentUser(): Promise<AuthUser | null> {
  const token = getAuthToken();
  if (!token) return null;
  const res = await fetch(`${BASE}/auth/me`, { headers: { Authorization: `Bearer ${token}` } });
  if (!res.ok) {
    setAuthToken(null); // stale/expired token - drop it rather than retry forever
    return null;
  }
  const data = await res.json();
  return { userId: data.user_id, email: data.email, name: data.name, token: data.token };
}
