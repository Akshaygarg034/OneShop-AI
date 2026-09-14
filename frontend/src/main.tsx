import { createRoot } from "react-dom/client";
import App from "./app/App.tsx";
import { BASE } from "./app/api/api";
import "./styles/index.css";

// Open the TCP+TLS connection to the API while React is still booting, so the
// first catalog request doesn't pay the handshake.
try {
  const link = document.createElement("link");
  link.rel = "preconnect";
  link.href = new URL(BASE).origin;
  document.head.appendChild(link);
} catch { /* invalid VITE_API_URL — nothing to preconnect to */ }

createRoot(document.getElementById("root")!).render(<App />);
