import type {
  Product, AppNotification, LiveActivity, RegisterPayload, LoginPayload, AuthUser,
  ShippingDetails, PaymentDetails, Preferences,
} from "../types";
import { getSessionId, setSessionId, getAuthToken, setAuthToken, clearSessionId } from "./session";

export const BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

export function authHeaders(): Record<string, string> {
  const token = getAuthToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function jsonHeaders(): Record<string, string> {
  return { "Content-Type": "application/json", ...authHeaders() };
}

// --- backend wire shapes (backend/app/contracts/models.py is the source of truth) ---
interface BackendProduct {
  id: string;
  type: string;
  name: string;
  brand: string;
  description: string;
  category: string;
  price_onetime: number;
  price_monthly: number;
  original_price: number;
  discount_pct: number;
  rating: number;
  review_count: number;
  colors: string[];
  model_year: number;
  warranty_months: number;
  features: string[];
  compatible_plans: string[];
  stock: number;
  in_stock: boolean;
  image_url: string;
  attributes: Record<string, unknown>;
}

interface BackendRecommendation {
  product_id: string;
  rank: number;
}

interface BackendChatResponse {
  reply_text: string;
  recommendations: BackendRecommendation[];
  products: BackendProduct[];
  nba: string[];
  conversation_id: string;
}

function titleCase(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function placeholderImage(name: string): string {
  return `https://placehold.co/400x400/1a1a2e/ffffff?text=${encodeURIComponent(name)}`;
}

function adaptProduct(p: BackendProduct, recommended = false): Product {
  const price = p.price_onetime > 0 ? p.price_onetime : p.price_monthly;
  const monthlyPrice = p.price_onetime > 0 ? 0 : p.price_monthly;

  const specBits: string[] = [];
  const attrs = p.attributes ?? {};
  if (attrs.ram_gb) specBits.push(`${attrs.ram_gb}GB RAM`);
  if (attrs.storage_gb) specBits.push(`${attrs.storage_gb}GB`);
  if (attrs.display_inch) specBits.push(`${attrs.display_inch}"`);
  if (attrs.battery_hours) specBits.push(`${attrs.battery_hours}h battery`);
  if (attrs.data_gb) specBits.push(Number(attrs.data_gb) >= 999 ? "Unlimited data" : `${attrs.data_gb}GB data`);

  // Only actual chat recommendations are "AI Picks" — badging the whole browse
  // grid would be meaningless noise.
  const badge = !p.in_stock
    ? "Out of Stock"
    : recommended
      ? "AI Pick"
      : p.discount_pct > 0
        ? `-${p.discount_pct}%`
        : "In Stock";

  return {
    id: p.id,
    name: p.name,
    brand: p.brand,
    category: titleCase(p.category || p.type),
    price,
    monthlyPrice,
    originalPrice: p.original_price > price ? p.original_price : 0,
    discountPct: p.discount_pct,
    image: p.image_url || placeholderImage(p.name),
    badge,
    badgeColor: !p.in_stock ? "#FF3B30" : recommended ? "var(--primary)" : p.discount_pct > 0 ? "#E4572E" : "#00C2A8",
    stars: p.rating,
    reviews: p.review_count,
    colors: p.colors ?? [],
    specs: specBits,
    attributes: attrs,
    tags: p.features.map(titleCase),
    inStock: p.in_stock,
    trend: p.in_stock ? `${p.stock} in stock` : "Currently unavailable",
  };
}

function adaptRecommended(products: BackendProduct[], recs: BackendRecommendation[]): Product[] {
  const byId = new Map(products.map((p) => [p.id, p]));
  return recs
    .map((rec) => {
      const raw = byId.get(rec.product_id);
      return raw ? adaptProduct(raw, true) : null;
    })
    .filter((p): p is Product => p !== null);
}

// --- catalog ---
async function fetchRawCatalog(): Promise<BackendProduct[]> {
  const res = await fetch(`${BASE}/catalog?session_id=${getSessionId()}`);
  if (!res.ok) throw new Error("Could not load the catalog. Please try again.");
  return res.json();
}

export function getProducts(): Promise<Product[]> {
  return fetchRawCatalog().then((raw) => raw.map((p) => adaptProduct(p)));
}

export async function getBundleSuggestions(excludeIds: string[]): Promise<Product[]> {
  const res = await fetch(`${BASE}/cart/suggestions?session_id=${getSessionId()}&limit=3`, {
    headers: authHeaders(),
  });
  if (!res.ok) return [];
  const raw: BackendProduct[] = await res.json();
  return raw.filter((p) => !excludeIds.includes(p.id)).map((p) => adaptProduct(p));
}

export function getNotifications(): Promise<AppNotification[]> {
  return Promise.resolve([]);
}

export async function getLiveActivity(productId: string): Promise<LiveActivity> {
  const res = await fetch(`${BASE}/catalog/${productId}`);
  if (!res.ok) return { viewers: 0, stockLeft: 0 };
  const p: BackendProduct = await res.json();
  return { viewers: 0, stockLeft: p.stock };
}

// --- chat ---
export interface HistoryMessage {
  role: "user" | "assistant";
  content: string;
  recommendations: BackendRecommendation[];
  created_at?: string;
}

export interface AssistantReply {
  reply: string;
  products?: Product[];
  conversationId: string;
}

interface SSEEvent {
  event: string;
  data: string;
}

function* parseSSE(buffer: string): Generator<SSEEvent> {
  for (const block of buffer.split("\n\n")) {
    let event = "message";
    const dataLines: string[] = [];
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
    }
    if (dataLines.length) yield { event, data: dataLines.join("\n") };
  }
}

/** Stream a chat turn. `onToken` receives reply-text deltas as they generate;
 * the resolved promise carries the final reply, product cards (embedded in the
 * stream — no extra catalog fetch), and the conversation id. */
export async function askAssistantStream(
  message: string,
  conversationId: string,
  onToken: (text: string) => void,
): Promise<AssistantReply> {
  const res = await fetch(`${BASE}/chat/stream`, {
    method: "POST",
    headers: jsonHeaders(),
    body: JSON.stringify({ session_id: getSessionId(), message, conversation_id: conversationId || undefined }),
  });
  if (!res.ok || !res.body) throw new Error("Chat stream unavailable");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let reply = "";
  let products: Product[] | undefined;
  let nba: string[] = [];
  let returnedConvId = conversationId;

  const handle = (evt: SSEEvent) => {
    const payload = JSON.parse(evt.data);
    if (evt.event === "token") {
      reply += payload.text;
      onToken(payload.text);
    } else if (evt.event === "recommendations") {
      products = adaptRecommended(payload.products, payload.recommendations);
    } else if (evt.event === "nba") {
      nba = payload.nba ?? [];
    } else if (evt.event === "done") {
      returnedConvId = payload.conversation_id || returnedConvId;
      reply = payload.reply_text || reply;
    } else if (evt.event === "error") {
      throw new Error(payload.detail || "Chat failed");
    }
  };

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lastBreak = buffer.lastIndexOf("\n\n");
    if (lastBreak === -1) continue;
    for (const evt of parseSSE(buffer.slice(0, lastBreak))) handle(evt);
    buffer = buffer.slice(lastBreak + 2);
  }
  for (const evt of parseSSE(buffer)) handle(evt);

  const fullReply = nba.length ? `${reply}\n\n${nba.join("\n")}` : reply;
  return { reply: fullReply, products, conversationId: returnedConvId };
}

/** Non-streaming fallback. */
export async function askAssistant(message: string, conversationId: string): Promise<AssistantReply> {
  const res = await fetch(`${BASE}/chat`, {
    method: "POST",
    headers: jsonHeaders(),
    body: JSON.stringify({ session_id: getSessionId(), message, conversation_id: conversationId || undefined }),
  });
  if (!res.ok) throw new Error("Sorry, I couldn't reach the assistant. Please try again.");
  const data: BackendChatResponse = await res.json();
  const products = data.recommendations.length
    ? adaptRecommended(data.products, data.recommendations)
    : undefined;
  const reply = data.nba.length ? `${data.reply_text}\n\n${data.nba.join("\n")}` : data.reply_text;
  return { reply, products, conversationId: data.conversation_id };
}

/** Restore product cards for assistant messages in a history list (one catalog fetch). */
export async function resolveHistoryProducts(
  history: HistoryMessage[],
): Promise<Map<number, Product[]>> {
  const hasAnyRecs = history.some((m) => m.role === "assistant" && m.recommendations?.length > 0);
  if (!hasAnyRecs) return new Map();

  const catalog = await fetchRawCatalog();
  const result = new Map<number, Product[]>();
  history.forEach((msg, i) => {
    if (msg.role !== "assistant" || !msg.recommendations?.length) return;
    const products = adaptRecommended(catalog, msg.recommendations);
    if (products.length) result.set(i, products);
  });
  return result;
}

export interface ConversationSummary {
  id: string;
  title: string;
  updatedAt: number; // ms epoch, 0 when unknown
}

export async function fetchConversations(): Promise<ConversationSummary[]> {
  const res = await fetch(`${BASE}/chat/conversations?session_id=${getSessionId()}`, {
    headers: authHeaders(),
  });
  if (!res.ok) return [];
  const data: { conversations?: { id: string; title: string; updated_at: string }[] } = await res.json();
  return (data.conversations ?? []).map((c) => ({
    id: c.id,
    title: c.title,
    updatedAt: c.updated_at ? Date.parse(c.updated_at) || 0 : 0,
  }));
}

export async function fetchChatHistory(conversationId?: string): Promise<{
  conversationId: string;
  history: HistoryMessage[];
}> {
  const params = new URLSearchParams({ session_id: getSessionId() });
  if (conversationId) params.set("conversation_id", conversationId);
  const res = await fetch(`${BASE}/chat/history?${params}`, { headers: authHeaders() });
  if (!res.ok) return { conversationId: conversationId ?? "", history: [] };
  const data: { conversation_id: string; history: HistoryMessage[] } = await res.json();
  return { conversationId: data.conversation_id ?? "", history: data.history ?? [] };
}

export async function deleteConversation(conversationId: string): Promise<boolean> {
  const res = await fetch(
    `${BASE}/chat/conversations/${encodeURIComponent(conversationId)}?session_id=${getSessionId()}`,
    { method: "DELETE", headers: authHeaders() },
  );
  return res.ok;
}

// --- preferences ---
export async function getPreferences(): Promise<Preferences | null> {
  const res = await fetch(`${BASE}/session/profile?session_id=${getSessionId()}`, {
    headers: authHeaders(),
  });
  if (!res.ok) return null;
  const data = await res.json();
  return data.profile as Preferences;
}

export async function clearPreference(
  section: "all" | "budget" | "brands" | "categories" | "features" | "attributes" | "rejected_products",
  removeKey?: string,
): Promise<Preferences | null> {
  const res = await fetch(`${BASE}/session/profile?session_id=${getSessionId()}`, {
    method: "PATCH",
    headers: jsonHeaders(),
    body: JSON.stringify({ clear: section, remove_key: removeKey }),
  });
  if (!res.ok) return null;
  const data = await res.json();
  return data.profile as Preferences;
}

// --- checkout ---
export interface OrderResult {
  orderNumber: string;
  estimatedDelivery: string;
}

export async function createOrder(
  _shipping: ShippingDetails,
  _payment: PaymentDetails,
  _items: unknown,
): Promise<OrderResult> {
  const res = await fetch(`${BASE}/cart/checkout`, {
    method: "POST",
    headers: jsonHeaders(),
    body: JSON.stringify({ session_id: getSessionId() }),
  });
  if (!res.ok) throw new Error("Could not place the order. Please try again.");
  const data: { order_id: string } = await res.json();
  const eta = new Date(Date.now() + 3 * 24 * 60 * 60 * 1000);
  return {
    orderNumber: data.order_id,
    estimatedDelivery: eta.toLocaleDateString("de-DE", { day: "2-digit", month: "short" }),
  };
}

// --- auth ---
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
  setAuthToken(data.token);
  setSessionId(data.user_id);
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
  setAuthToken(data.token);
  setSessionId(data.user_id);
  return { userId: data.user_id, email: data.email, name: data.name, token: data.token };
}

/** Exchanges a Google ID token for our own session token. */
export async function loginWithGoogle(credential: string): Promise<AuthUser> {
  const res = await fetch(`${BASE}/auth/google`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ credential, session_id: getSessionId() }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => null);
    throw new Error(err?.detail || "Google sign-in failed. Please try again.");
  }
  const data = await res.json();
  setAuthToken(data.token);
  setSessionId(data.user_id);
  return { userId: data.user_id, email: data.email, name: data.name, token: data.token };
}

export function logoutUser(): void {
  setAuthToken(null);
  clearSessionId();
}

export async function getCurrentUser(): Promise<AuthUser | null> {
  const token = getAuthToken();
  if (!token) return null;
  const res = await fetch(`${BASE}/auth/me`, { headers: { Authorization: `Bearer ${token}` } });
  if (!res.ok) {
    setAuthToken(null);
    return null;
  }
  const data = await res.json();
  return { userId: data.user_id, email: data.email, name: data.name, token: data.token };
}
