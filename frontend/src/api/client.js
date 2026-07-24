// Thin API client. SHARED.
// Every feature calls the backend through these helpers - do not fetch() directly elsewhere.

const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

// The SAME session id is used by OneShop (web) and OneApp (mobile) -> omnichannel.
export function getSessionId() {
  let id = localStorage.getItem("session_id");
  if (!id) {
    id = "shopper-1";
    localStorage.setItem("session_id", id);
  }
  return id;
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

export const addToCart = (product_id, qty = 1) =>
  post("/cart/add", { session_id: getSessionId(), product_id, qty });

export const removeFromCart = (product_id) =>
  post("/cart/remove", { session_id: getSessionId(), product_id });

export const checkout = () =>
  post("/cart/checkout", { session_id: getSessionId() });
