// Thin API client. SHARED.
// Every feature calls the backend through these helpers - do not fetch() directly elsewhere.

const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

// The SAME session id is used by OneShop (web) and OneApp (mobile) -> omnichannel.
//
// Resolution order (P4): URL ?session= param  >  localStorage  >  default.
// The URL param is what makes the handoff work across *separate* windows/devices
// (a second browser, a phone, an incognito tab) - not just channel-toggling inside
// one tab. Whatever we resolve is written back to localStorage so it sticks.
const DEFAULT_SESSION = "shopper-1";

export function getSessionId() {
  const fromUrl = new URLSearchParams(window.location.search).get("session");
  let id = fromUrl || localStorage.getItem("session_id") || DEFAULT_SESSION;
  localStorage.setItem("session_id", id);
  return id;
}

// Point a second device/window at the SAME session (e.g. behind a "continue on
// mobile" button or a QR code). ?channel=mobile just hints the UI to open OneApp.
export function getHandoffUrl(channel = "mobile") {
  const url = new URL(window.location.href);
  url.searchParams.set("session", getSessionId());
  if (channel) url.searchParams.set("channel", channel);
  return url.toString();
}

// Optional deep-link hint the UI can read to open the mobile view on load.
export function getChannelFromUrl() {
  return new URLSearchParams(window.location.search).get("channel");
}

async function post(path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${path} failed: ${res.status}`);
  return res.json();
}

export const sendChat = (message) =>
  post("/chat", { session_id: getSessionId(), message });

export const getCatalog = async () => {
  const res = await fetch(`${BASE}/catalog`);
  return res.json();
};

export const getCart = async () => {
  const res = await fetch(`${BASE}/cart?session_id=${getSessionId()}`);
  return res.json();
};

// Read-only summary for the checkout review screen (split totals + free-shipping).
export const getCartSummary = async () => {
  const res = await fetch(`${BASE}/cart/summary?session_id=${getSessionId()}`);
  return res.json();
};

export const addToCart = (product_id, qty = 1) =>
  post("/cart/add", { session_id: getSessionId(), product_id, qty });

export const removeFromCart = (product_id) =>
  post("/cart/remove", { session_id: getSessionId(), product_id });

export const checkout = () =>
  post("/cart/checkout", { session_id: getSessionId() });
