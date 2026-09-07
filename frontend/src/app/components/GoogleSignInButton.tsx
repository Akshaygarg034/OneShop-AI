import { useEffect, useRef, useState } from "react";
import { useTheme } from "../theme/ThemeProvider";

const CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || "";
const GIS_SRC = "https://accounts.google.com/gsi/client";

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: Record<string, unknown>) => void;
          renderButton: (parent: HTMLElement, options: Record<string, unknown>) => void;
        };
      };
    };
  }
}

/** Loaded once per page, not once per mount — GIS complains if injected twice. */
let gisLoader: Promise<void> | null = null;

function loadGis(): Promise<void> {
  if (gisLoader) return gisLoader;
  gisLoader = new Promise((resolve, reject) => {
    if (window.google?.accounts?.id) return resolve();
    const script = document.createElement("script");
    script.src = GIS_SRC;
    script.async = true;
    script.defer = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Could not reach Google. Check your connection."));
    document.head.appendChild(script);
  });
  return gisLoader;
}

interface GoogleSignInButtonProps {
  /** Receives the Google ID token to hand to the backend. */
  onCredential: (credential: string) => void;
  onError: (message: string) => void;
  mode: "login" | "register";
}

export function GoogleSignInButton({ onCredential, onError, mode }: GoogleSignInButtonProps) {
  const ref = useRef<HTMLDivElement>(null);
  const { theme } = useTheme();
  const [ready, setReady] = useState(false);
  // Keeps the GIS callback pointing at the latest handlers without re-rendering
  // the button, which would make it flicker on every parent state change.
  const handler = useRef(onCredential);
  handler.current = onCredential;

  useEffect(() => {
    if (!CLIENT_ID) return;
    let cancelled = false;

    loadGis()
      .then(() => {
        if (cancelled || !ref.current || !window.google) return;
        window.google.accounts.id.initialize({
          client_id: CLIENT_ID,
          callback: (res: { credential?: string }) => {
            if (res.credential) handler.current(res.credential);
            else onError("Google did not return a sign-in token.");
          },
        });
        ref.current.innerHTML = "";
        window.google.accounts.id.renderButton(ref.current, {
          type: "standard",
          theme: theme === "dark" ? "filled_black" : "outline",
          size: "large",
          shape: "pill",
          text: mode === "register" ? "signup_with" : "signin_with",
          logo_alignment: "center",
          width: 320,
        });
        setReady(true);
      })
      .catch((err: Error) => !cancelled && onError(err.message));

    return () => {
      cancelled = true;
    };
    // Re-rendered on theme/mode change so the button matches the surrounding UI.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [theme, mode]);

  // Nothing configured on this deployment — fall back to email/password silently.
  if (!CLIENT_ID) return null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14, marginBottom: 4 }}>
      <div ref={ref} style={{ display: "flex", justifyContent: "center", minHeight: ready ? undefined : 44 }} />
      <div className="flex items-center" style={{ gap: 10 }}>
        <span style={{ flex: 1, height: 1, background: "var(--border)" }} />
        <span style={{ fontSize: 10.5, fontWeight: 600, letterSpacing: "0.08em", color: "var(--muted-foreground)" }}>
          OR
        </span>
        <span style={{ flex: 1, height: 1, background: "var(--border)" }} />
      </div>
    </div>
  );
}
