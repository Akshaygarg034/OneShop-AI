// Session identity.
//
// Every guest browser gets its own random session_id (persisted in localStorage),
// so carts/history don't leak between visitors. Once someone registers/logs in,
// the backend merges the guest session into a session keyed by their user_id and
// we switch to that as the session_id — permanent, cross-device identity.
const SESSION_KEY = "session_id";

function randomGuestId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `guest-${crypto.randomUUID()}`;
  }
  return `guest-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function getSessionId(): string {
  const id = localStorage.getItem(SESSION_KEY) || randomGuestId();
  localStorage.setItem(SESSION_KEY, id);
  return id;
}

// Called after register/login: from now on, use the permanent user_id.
// Fires an event so already-mounted contexts (e.g. the cart) can re-fetch
// under the new identity instead of only picking it up on next page load.
export function setSessionId(id: string): void {
  localStorage.setItem(SESSION_KEY, id);
  window.dispatchEvent(new Event("oneshop-session-changed"));
}

// Called on logout: start a fresh anonymous session so the previous user's
// cart and history are not visible to the next visitor on this device.
export function clearSessionId(): void {
  localStorage.setItem(SESSION_KEY, randomGuestId());
  window.dispatchEvent(new Event("oneshop-session-changed"));
}

export function getAuthToken(): string | null {
  return localStorage.getItem("auth_token");
}

export function setAuthToken(token: string | null): void {
  if (token) localStorage.setItem("auth_token", token);
  else localStorage.removeItem("auth_token");
}
