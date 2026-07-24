import { useEffect, useRef, useState } from "react";
import { Search, ShoppingCart, Mic, LogOut } from "lucide-react";
import { ThemeSwitcher } from "./ThemeSwitcher";
import { Logo } from "./Logo";
import { AuthModal } from "./AuthModal";
import { useCart } from "../cart/CartContext";
import { useAuth } from "../auth/AuthContext";
import { useSpeechRecognition } from "../lib/useSpeechRecognition";

export type View = "discovery" | "cart";

interface StoreHeaderProps {
  activeView: View;
  onViewChange: (view: View) => void;
  searchQuery: string;
  onSearchChange: (query: string) => void;
}

function initialsFor(name: string, email: string): string {
  const source = name.trim() || email;
  const parts = source.trim().split(/\s+/);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return source.slice(0, 2).toUpperCase();
}

function UserMenu() {
  const { user, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const [authOpen, setAuthOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpen) return;
    const onClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    };
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, [menuOpen]);

  if (!user) {
    return (
      <>
        <button
          onClick={() => setAuthOpen(true)}
          style={{
            background: "var(--primary)",
            border: "none",
            borderRadius: 50,
            padding: "7px 16px",
            cursor: "pointer",
            color: "#fff",
            fontSize: 13,
            fontWeight: 700,
            flexShrink: 0,
          }}
        >
          Sign in
        </button>
        <AuthModal open={authOpen} onClose={() => setAuthOpen(false)} />
      </>
    );
  }

  return (
    <div ref={menuRef} style={{ position: "relative", flexShrink: 0 }}>
      <button
        onClick={() => setMenuOpen((o) => !o)}
        title={user.name || user.email}
        style={{
          width: 32,
          height: 32,
          borderRadius: "50%",
          background: "var(--primary)",
          border: "none",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 11,
          fontWeight: 700,
          color: "#fff",
          cursor: "pointer",
        }}
      >
        {initialsFor(user.name, user.email)}
      </button>

      {menuOpen && (
        <div
          style={{
            position: "absolute",
            top: "calc(100% + 8px)",
            right: 0,
            minWidth: 200,
            background: "var(--card)",
            border: "1px solid var(--border)",
            borderRadius: 14,
            boxShadow: "0 12px 32px rgba(0,0,0,0.2)",
            padding: 6,
            zIndex: 40,
          }}
        >
          <div style={{ padding: "8px 10px", borderBottom: "1px solid var(--border)", marginBottom: 4 }}>
            <p style={{ fontSize: 12.5, fontWeight: 700, color: "var(--foreground)", lineHeight: 1.3 }}>
              {user.name || "Account"}
            </p>
            <p style={{ fontSize: 11, color: "var(--muted-foreground)", lineHeight: 1.3 }}>{user.email}</p>
          </div>
          <button
            onClick={() => {
              logout();
              setMenuOpen(false);
            }}
            className="flex items-center gap-2"
            style={{
              width: "100%",
              background: "none",
              border: "none",
              borderRadius: 10,
              padding: "8px 10px",
              cursor: "pointer",
              color: "var(--foreground)",
              fontSize: 12.5,
              fontWeight: 600,
              textAlign: "left",
            }}
          >
            <LogOut size={13} />
            Log out
          </button>
        </div>
      )}
    </div>
  );
}

export function StoreHeader({ activeView, onViewChange, searchQuery, onSearchChange }: StoreHeaderProps) {
  const { count: cartCount } = useCart();

  const { listening, supported: micSupported, toggleListening } = useSpeechRecognition((transcript) => {
    onSearchChange(transcript);
  });

  return (
    <header style={{ flexShrink: 0, background: "var(--surface)" }}>
      <div
        className="flex items-center gap-6 px-6 lg:px-8"
        style={{ height: 64, borderBottom: "1px solid var(--border)", maxWidth: 1280, margin: "0 auto", width: "100%" }}
      >
        <button
          onClick={() => onViewChange("discovery")}
          className="flex items-center gap-2 flex-shrink-0"
          style={{ background: "none", border: "none", cursor: "pointer" }}
        >
          <Logo size={32} />
          <span style={{ fontSize: 17, fontWeight: 800, color: "var(--foreground)" }}>OneShop</span>
        </button>

        <div className="flex-1 relative" style={{ maxWidth: 420, margin: "0 auto" }}>
          <Search
            size={14}
            style={{ position: "absolute", left: 14, top: "50%", transform: "translateY(-50%)", color: "var(--muted-foreground)" }}
          />
          <input
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && onViewChange("discovery")}
            placeholder="Search products..."
            style={{
              width: "100%",
              background: "var(--input-background)",
              border: "1.5px solid rgba(var(--primary-rgb),0.25)",
              borderRadius: 50,
              padding: "9px 36px",
              fontSize: 13,
              color: "var(--foreground)",
              outline: "none",
            }}
            onFocus={(e) => (e.target.style.borderColor = "var(--primary)")}
            onBlur={(e) => (e.target.style.borderColor = "rgba(var(--primary-rgb),0.25)")}
          />
          {micSupported && (
            <button
              onClick={toggleListening}
              title="Search by voice"
              style={{
                position: "absolute", right: 8, top: "50%", transform: "translateY(-50%)",
                background: listening ? "rgba(var(--primary-rgb),0.15)" : "transparent",
                border: "none", cursor: "pointer", padding: 4, borderRadius: 50,
                color: listening ? "var(--primary)" : "var(--muted-foreground)",
              }}
            >
              <Mic size={13} />
            </button>
          )}
        </div>

        <div className="flex items-center gap-3 flex-shrink-0">
          <ThemeSwitcher />

          <button
            onClick={() => onViewChange("cart")}
            style={{
              position: "relative",
              display: "flex",
              alignItems: "center",
              gap: 6,
              background: activeView === "cart" ? "var(--primary)" : "transparent",
              border: `1.5px solid ${activeView === "cart" ? "var(--primary)" : "var(--foreground)"}`,
              borderRadius: 50,
              padding: "7px 14px",
              cursor: "pointer",
              color: activeView === "cart" ? "#fff" : "var(--foreground)",
              fontSize: 13,
              fontWeight: 700,
            }}
          >
            <ShoppingCart size={15} />
            <span className="hidden sm:inline">Cart</span>
            {cartCount > 0 && (
              <span
                style={{
                  background: activeView === "cart" ? "#fff" : "var(--primary)",
                  color: activeView === "cart" ? "var(--primary)" : "#fff",
                  borderRadius: "50%",
                  width: 18, height: 18, fontSize: 10, fontWeight: 700,
                  display: "flex", alignItems: "center", justifyContent: "center",
                }}
              >
                {cartCount}
              </span>
            )}
          </button>

          <UserMenu />
        </div>
      </div>
    </header>
  );
}
