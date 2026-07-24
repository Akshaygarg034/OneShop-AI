import { Search, ShoppingCart, Mic } from "lucide-react";
import { ThemeSwitcher } from "./ThemeSwitcher";
import { Logo } from "./Logo";
import { useCart } from "../cart/CartContext";
import { useSpeechRecognition } from "../lib/useSpeechRecognition";

export type View = "discovery" | "cart";

interface NavLink {
  label: string;
  category: string;
}

const navLinks: NavLink[] = [
  { label: "Home", category: "All" },
  { label: "Phones", category: "Phones" },
  { label: "Plans", category: "Plans" },
  { label: "Accessories", category: "Accessories" },
  { label: "Deals", category: "Bundles" },
];

interface StoreHeaderProps {
  activeView: View;
  onViewChange: (view: View) => void;
  category: string;
  onCategoryChange: (category: string) => void;
  searchQuery: string;
  onSearchChange: (query: string) => void;
}

export function StoreHeader({ activeView, onViewChange, category, onCategoryChange, searchQuery, onSearchChange }: StoreHeaderProps) {
  const { count: cartCount } = useCart();

  const { listening, supported: micSupported, toggleListening } = useSpeechRecognition((transcript) => {
    onSearchChange(transcript);
  });

  return (
    <header style={{ flexShrink: 0, background: "var(--surface)" }}>
      <div
        className="flex items-center gap-8 px-8"
        style={{ height: 72, borderBottom: "1px solid var(--border)", maxWidth: 1280, margin: "0 auto", width: "100%" }}
      >
        <button
          onClick={() => onViewChange("discovery")}
          className="flex items-center gap-2 flex-shrink-0"
          style={{ background: "none", border: "none", cursor: "pointer" }}
        >
          <Logo size={34} />
          <span style={{ fontSize: 17, fontWeight: 800, color: "var(--foreground)" }}>OneShop</span>
        </button>

        <nav className="hidden md:flex items-center gap-7" style={{ flexShrink: 0 }}>
          {navLinks.map((link) => {
            const active = activeView === "discovery" && category === link.category;
            return (
              <button
                key={link.label}
                onClick={() => {
                  onCategoryChange(link.category);
                  onViewChange("discovery");
                }}
                style={{
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  fontSize: 13.5,
                  fontWeight: 500,
                  padding: 0,
                  color: active ? "var(--primary)" : "var(--foreground)",
                  opacity: active ? 1 : 0.75,
                }}
              >
                {link.label}
              </button>
            );
          })}
        </nav>

        <div className="hidden sm:block flex-1 relative" style={{ maxWidth: 320 }}>
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
              padding: "9px 36px 9px 36px",
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

        <div className="flex items-center gap-4 flex-shrink-0" style={{ marginLeft: "auto" }}>
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
              padding: "8px 16px",
              cursor: "pointer",
              color: activeView === "cart" ? "#fff" : "var(--foreground)",
              fontSize: 13,
              fontWeight: 700,
            }}
          >
            <ShoppingCart size={15} />
            Cart
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

          <div
            style={{
              width: 34, height: 34, borderRadius: "50%", background: "linear-gradient(135deg, var(--primary), #7B61FF)",
              display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, fontWeight: 700, color: "#fff",
              cursor: "pointer", flexShrink: 0,
            }}
          >
            JM
          </div>
        </div>
      </div>
    </header>
  );
}
