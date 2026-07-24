import { useState } from "react";
import { StoreHeader, type View } from "./components/StoreHeader";
import { Discovery } from "./components/views/Discovery";
import { SmartCart } from "./components/views/SmartCart";
import { SiteFooter } from "./components/SiteFooter";
import { FloatingChat } from "./components/FloatingChat";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { ThemeProvider } from "./theme/ThemeProvider";
import { AuthProvider } from "./auth/AuthContext";
import { CartProvider } from "./cart/CartContext";

export default function App() {
  const [view, setView] = useState<View>("discovery");
  const [category, setCategory] = useState("All");
  const [searchQuery, setSearchQuery] = useState("");

  return (
    <ThemeProvider>
      <AuthProvider>
        <CartProvider>
          <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", background: "var(--background)", color: "var(--foreground)" }}>
            <div style={{ position: "sticky", top: 0, zIndex: 30 }}>
              <StoreHeader
                activeView={view}
                onViewChange={setView}
                searchQuery={searchQuery}
                onSearchChange={setSearchQuery}
              />
              <div style={{ background: "var(--primary)", padding: "9px 24px", textAlign: "center" }}>
                <p style={{ color: "#fff", fontWeight: 700, fontSize: 11.5, letterSpacing: "0.1em", textTransform: "uppercase" }}>
                  Smarter Shopping
                </p>
              </div>
            </div>

            <main style={{ flex: 1 }}>
              <ErrorBoundary label={view === "cart" ? "cart" : "product catalog"} key={view}>
                {view === "discovery" && (
                  <Discovery category={category} onCategoryChange={setCategory} searchQuery={searchQuery} />
                )}
                {view === "cart" && (
                  <SmartCart onContinueShopping={() => setView("discovery")} />
                )}
              </ErrorBoundary>
            </main>

            <SiteFooter />
            <ErrorBoundary label="chat assistant">
              <FloatingChat />
            </ErrorBoundary>
          </div>

          <style>{`
            * { box-sizing: border-box; }
            ::selection { background: rgba(var(--primary-rgb), 0.3); }
          `}</style>
        </CartProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}
