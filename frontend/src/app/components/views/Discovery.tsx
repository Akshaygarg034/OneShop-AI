import { useEffect, useState } from "react";
import { ShoppingCart, Star, TrendingUp, Check, RefreshCw } from "lucide-react";
import { useCart } from "../../cart/CartContext";
import { getProducts } from "../../api/api";
import { formatEUR } from "../../lib/format";
import { ColorDots } from "../ColorDots";
import type { Product } from "../../types";

const categories = ["All", "Smartphones", "Tablets", "Laptops", "Wearables", "Audio", "Accessories", "Plans", "Bundles"];

const SkeletonCard = () => (
  <div
    className="animate-pulse"
    style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 20, overflow: "hidden" }}
  >
    <div style={{ height: 180, background: "var(--muted)" }} />
    <div style={{ padding: "14px 16px" }}>
      <div style={{ height: 10, width: "40%", background: "var(--muted)", borderRadius: 4, marginBottom: 8 }} />
      <div style={{ height: 14, width: "80%", background: "var(--muted)", borderRadius: 4, marginBottom: 14 }} />
      <div style={{ height: 32, background: "var(--muted)", borderRadius: 8 }} />
    </div>
  </div>
);

interface DiscoveryProps {
  category: string;
  onCategoryChange: (category: string) => void;
  searchQuery: string;
}

export function Discovery({ category, onCategoryChange, searchQuery }: DiscoveryProps) {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { addItem, removeItem, isInCart } = useCart();

  const loadProducts = () => {
    setLoading(true);
    setError(null);
    getProducts()
      .then(setProducts)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadProducts();
  }, []);

  const query = searchQuery.trim().toLowerCase();
  const filtered = products
    .filter((p) => category === "All" || p.category === category)
    .filter((p) => !query || p.name.toLowerCase().includes(query) || p.tags.some((t) => t.toLowerCase().includes(query)));

  return (
    <div className="max-w-screen-xl mx-auto px-4 sm:px-8 py-8 sm:py-10" style={{ color: "var(--foreground)" }}>
      {/* Hero */}
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: "clamp(24px, 6vw, 34px)", fontWeight: 800, color: "var(--foreground)", marginBottom: 10, lineHeight: 1.15 }}>
          Shop smarter with AI.
        </h1>
        <p style={{ fontSize: 14, color: "var(--muted-foreground-2)", maxWidth: 520 }}>
          Personalized picks across phones, tablets, laptops, audio, and plans — matched to what you actually need.
        </p>
      </div>

      {/* Category tabs — horizontally scrollable so they never overflow the page on mobile */}
      <div style={{ marginBottom: 20 }}>
        <div
          className="flex items-center gap-2"
          style={{ overflowX: "auto", scrollbarWidth: "none", msOverflowStyle: "none", paddingBottom: 2 }}
        >
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => onCategoryChange(cat)}
              style={{
                flexShrink: 0,
                padding: "7px 16px",
                borderRadius: 50,
                fontSize: 12.5,
                fontWeight: 600,
                borderWidth: 1.5,
                borderStyle: "solid",
                cursor: "pointer",
                transition: "all 0.2s",
                background: category === cat ? "var(--primary)" : "transparent",
                borderColor: category === cat ? "var(--primary)" : "var(--border)",
                color: category === cat ? "#fff" : "var(--foreground)",
              }}
            >
              {cat}
            </button>
          ))}
        </div>
        {!loading && (
          <div style={{ marginTop: 8, fontSize: 11.5, color: "var(--muted-foreground)", textAlign: "right" }}>
            {filtered.length} products
          </div>
        )}
      </div>

      {/* Error state */}
      {error && (
        <div
          className="flex items-center justify-between"
          style={{ background: "rgba(255,59,48,0.08)", border: "1px solid rgba(255,59,48,0.25)", borderRadius: 10, padding: "14px 18px", marginBottom: 20 }}
        >
          <span style={{ fontSize: 13, color: "#FF3B30" }}>{error}</span>
          <button
            onClick={loadProducts}
            style={{ display: "flex", alignItems: "center", gap: 6, background: "none", border: "1px solid rgba(255,59,48,0.3)", color: "#FF3B30", borderRadius: 8, padding: "6px 12px", fontSize: 12, cursor: "pointer" }}
          >
            <RefreshCw size={12} /> Retry
          </button>
        </div>
      )}

      {/* Product Grid */}
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      ) : filtered.length === 0 && !error ? (
        <div style={{ textAlign: "center", padding: "60px 0", color: "var(--muted-foreground)" }}>
          No products match your filters right now.
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {filtered.map((product) => {
            const inCart = isInCart(product.id);
            return (
              <div
                key={product.id}
                style={{
                  background: "var(--card)",
                  border: "1px solid var(--border)",
                  borderRadius: 20,
                  overflow: "hidden",
                  transition: "box-shadow 0.2s, transform 0.2s",
                }}
                onMouseEnter={(e) => {
                  (e.currentTarget as HTMLDivElement).style.boxShadow = "0 12px 32px rgba(0,0,0,0.08)";
                  (e.currentTarget as HTMLDivElement).style.transform = "translateY(-2px)";
                }}
                onMouseLeave={(e) => {
                  (e.currentTarget as HTMLDivElement).style.boxShadow = "none";
                  (e.currentTarget as HTMLDivElement).style.transform = "translateY(0)";
                }}
              >
                {/* Image area */}
                <div style={{ position: "relative", height: 180, background: "var(--muted)", overflow: "hidden" }}>
                  <img
                    src={product.image}
                    alt={product.name}
                    style={{
                      width: "100%",
                      height: "100%",
                      objectFit: "cover",
                      objectPosition: "center",
                      display: "block",
                      opacity: product.inStock ? 1 : 0.5,
                    }}
                  />
                  <div style={{ position: "absolute", top: 10, left: 10, display: "flex", gap: 6 }}>
                    <span
                      style={{
                        fontSize: 9,
                        fontWeight: 700,
                        padding: "3px 8px",
                        borderRadius: 20,
                        background: product.badgeColor,
                        color: "#fff",
                      }}
                    >
                      {product.badge}
                    </span>
                  </div>
                  {!product.inStock && (
                    <div
                      style={{
                        position: "absolute",
                        bottom: 0,
                        left: 0,
                        right: 0,
                        background: "rgba(0,0,0,0.7)",
                        padding: "6px",
                        textAlign: "center",
                        fontSize: 10,
                        color: "#FFD700",
                      }}
                    >
                      {product.trend}
                    </div>
                  )}
                </div>

                {/* Content */}
                <div style={{ padding: "14px 16px" }}>
                  <div style={{ marginBottom: 8 }}>
                    <span style={{ fontSize: 10, color: "var(--muted-foreground)" }}>
                      {product.brand ? `${product.brand} · ` : ""}{product.category}
                    </span>
                    <div className="flex items-center justify-between gap-2">
                      <p style={{ fontSize: 14, fontWeight: 600, color: "var(--foreground)", lineHeight: 1.3 }}>{product.name}</p>
                      <ColorDots colors={product.colors} />
                    </div>
                  </div>

                  <div className="flex flex-wrap gap-1.5 mb-3">
                    {(product.specs.length ? product.specs : product.tags).slice(0, 4).map((tag) => (
                      <span
                        key={tag}
                        style={{
                          fontSize: 9,
                          padding: "2px 7px",
                          borderRadius: 20,
                          background: "var(--muted)",
                          border: "1px solid rgba(var(--border-rgb),0.08)",
                          color: "var(--muted-foreground-2)",
                        }}
                      >
                        {tag}
                      </span>
                    ))}
                  </div>

                  <div className="flex items-center justify-between mb-3">
                    {product.reviews > 0 ? (
                      <div className="flex items-center gap-1">
                        <Star size={11} style={{ color: "#FFD700", fill: "#FFD700" }} />
                        <span style={{ fontSize: 11, color: "var(--foreground)", fontWeight: 600 }}>{product.stars}</span>
                        <span style={{ fontSize: 10, color: "var(--muted-foreground)" }}>({product.reviews.toLocaleString()})</span>
                      </div>
                    ) : <span />}
                    {product.inStock && (
                      <div className="flex items-center gap-1">
                        <TrendingUp size={10} style={{ color: "#22C55E" }} />
                        <span style={{ fontSize: 10, color: "#22C55E" }}>{product.trend}</span>
                      </div>
                    )}
                  </div>

                  <div className="flex items-baseline gap-2 mb-4">
                    <span style={{ fontSize: 18, fontWeight: 700, color: "var(--foreground)" }}>{formatEUR(product.price)}</span>
                    {product.originalPrice > 0 && (
                      <span style={{ fontSize: 12, color: "var(--muted-foreground)", textDecoration: "line-through" }}>
                        {formatEUR(product.originalPrice)}
                      </span>
                    )}
                    {product.monthlyPrice > 0 && (
                      <span style={{ fontSize: 11, color: "var(--muted-foreground)" }}>or {formatEUR(product.monthlyPrice)}/mo</span>
                    )}
                  </div>

                  <div className="flex gap-2">
                    <button
                      disabled={!product.inStock}
                      onClick={() => {
                        inCart ? removeItem(product.id) : addItem(product);
                      }}
                      style={{
                        flex: 1,
                        padding: "9px",
                        borderRadius: 50,
                        border: "none",
                        cursor: product.inStock ? "pointer" : "not-allowed",
                        opacity: product.inStock ? 1 : 0.5,
                        fontSize: 12,
                        fontWeight: 700,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        gap: 6,
                        background: inCart ? "#22C55E" : "var(--primary)",
                        color: "#fff",
                        transition: "all 0.2s",
                      }}
                    >
                      {inCart ? <Check size={13} /> : <ShoppingCart size={13} />}
                      {inCart ? "In Cart" : product.inStock ? "Add to Cart" : "Out of Stock"}
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
