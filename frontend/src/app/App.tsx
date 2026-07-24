import { useState } from "react";
import { StoreHeader, type View } from "./components/StoreHeader";
import { Discovery } from "./components/views/Discovery";
import { SmartCart } from "./components/views/SmartCart";
import { SiteFooter } from "./components/SiteFooter";
import { FloatingChat } from "./components/FloatingChat";
import { ThemeProvider } from "./theme/ThemeProvider";
import { CartProvider } from "./cart/CartContext";

export default function App() {
  const [view, setView] = useState<View>("discovery");
  const [category, setCategory] = useState("All");
  const [searchQuery, setSearchQuery] = useState("");

  return (
    <ThemeProvider>
      <CartProvider>
        <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", background: "var(--background)", color: "var(--foreground)" }}>
          <div style={{ position: "sticky", top: 0, zIndex: 30 }}>
            <StoreHeader
              activeView={view}
              onViewChange={setView}
              category={category}
              onCategoryChange={setCategory}
              searchQuery={searchQuery}
              onSearchChange={setSearchQuery}
            />
            <div style={{ background: "var(--primary)", padding: "9px 24px", textAlign: "center" }}>
              <p style={{ color: "#fff", fontWeight: 700, fontSize: 11.5, letterSpacing: "0.1em", textTransform: "uppercase" }}>
                Smarter Shopping, Powered by AI
              </p>
            </div>
          </div>

          <main style={{ flex: 1 }}>
            {view === "discovery" && (
              <Discovery category={category} onCategoryChange={setCategory} searchQuery={searchQuery} />
            )}
            {view === "cart" && (
              <SmartCart onContinueShopping={() => setView("discovery")} />
            )}
          </main>

          <SiteFooter />
          <FloatingChat />
        </div>

        <style>{`
          * { box-sizing: border-box; }
          ::selection { background: rgba(var(--primary-rgb), 0.3); }
        `}</style>
      </CartProvider>
    </ThemeProvider>
  );
}
