import { useEffect, useState } from "react";
import { X, Trash2 } from "lucide-react";
import { getPreferences, clearPreference } from "../api/api";
import type { BudgetPreference, Preferences } from "../types";

type Section = "brands" | "categories" | "features" | "attributes" | "rejected_products";

function titleCase(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function budgetLabel(category: string, budget: BudgetPreference): string {
  const unit = budget.period === "monthly" ? "/mo" : "";
  const range =
    budget.min != null && budget.max != null
      ? `€${budget.min} – €${budget.max}${unit}`
      : budget.max != null
        ? `up to €${budget.max}${unit}`
        : `from €${budget.min}${unit}`;
  const scope = category === "any" ? "Overall" : titleCase(category);
  return `${scope}: ${range}${budget.source === "inferred" ? " (inferred from purchases)" : ""}`;
}

function attributeLabel(name: string, c: { min?: number; max?: number; values?: string[] }): string {
  if (c.values?.length) return `${titleCase(name)}: ${c.values.join(", ")}`;
  const parts: string[] = [];
  if (c.min != null) parts.push(`≥ ${c.min}`);
  if (c.max != null) parts.push(`≤ ${c.max}`);
  return `${titleCase(name)} ${parts.join(" and ")}`;
}

function Chip({ label, tone, onRemove }: {
  label: string;
  tone: "positive" | "negative" | "excluded" | "neutral";
  onRemove: () => void;
}) {
  const colors = {
    positive: { bg: "rgba(0,194,168,0.12)", fg: "#00907c" },
    negative: { bg: "rgba(228,87,46,0.10)", fg: "#c4471f" },
    excluded: { bg: "rgba(255,59,48,0.12)", fg: "#d02a20" },
    neutral: { bg: "var(--muted)", fg: "var(--muted-foreground)" },
  }[tone];
  return (
    <span
      style={{
        display: "inline-flex", alignItems: "center", gap: 5,
        padding: "4px 6px 4px 10px", borderRadius: 999,
        background: colors.bg, color: colors.fg,
        fontSize: 11.5, fontWeight: 600,
      }}
    >
      {label}
      <button
        onClick={onRemove}
        title="Forget this"
        style={{
          background: "none", border: "none", cursor: "pointer", display: "flex",
          alignItems: "center", padding: 2, borderRadius: "50%", color: "inherit", opacity: 0.7,
        }}
      >
        <X size={11} />
      </button>
    </span>
  );
}

export function PreferencesPanel() {
  const [prefs, setPrefs] = useState<Preferences | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getPreferences()
      .then(setPrefs)
      .finally(() => setLoading(false));
  }, []);

  const clear = (section: "all" | "budget" | Section, key?: string) => {
    clearPreference(section, key).then((updated) => updated && setPrefs(updated));
  };

  if (loading) {
    return (
      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center",
                    color: "var(--muted-foreground)", fontSize: 13 }}>
        Loading…
      </div>
    );
  }

  const budgets = Object.entries(prefs?.budgets ?? {});
  const brands = Object.entries(prefs?.brands ?? {});
  const excluded = brands.filter(([, a]) => a.hard && a.score < 0);
  const liked = brands.filter(([, a]) => !a.hard && a.score > 0);
  const disliked = brands.filter(([, a]) => !a.hard && a.score < 0);
  const categories = Object.entries(prefs?.categories ?? {}).filter(([, a]) => a.score !== 0);
  const features = Object.entries(prefs?.features ?? {}).filter(([, a]) => a.score > 0);
  const attributes = Object.entries(prefs?.attributes ?? {});
  const rejected = Object.entries(prefs?.rejected_products ?? {});

  const isEmpty =
    !budgets.length && !brands.length && !categories.length && !features.length &&
    !attributes.length && !rejected.length;

  const SectionTitle = ({ children }: { children: React.ReactNode }) => (
    <p style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: "0.08em",
                textTransform: "uppercase", color: "var(--muted-foreground)", margin: "0 0 8px" }}>
      {children}
    </p>
  );

  return (
    <div style={{ flex: 1, overflowY: "auto", padding: 16, display: "flex",
                  flexDirection: "column", gap: 18, scrollbarWidth: "none" }}>
      <p style={{ fontSize: 12, color: "var(--muted-foreground)", margin: 0, lineHeight: 1.5 }}>
        What the assistant has learned from your chats and shopping. Remove anything
        and it stops shaping your recommendations immediately.
      </p>

      {isEmpty && (
        <div style={{ padding: "32px 8px", textAlign: "center", color: "var(--muted-foreground)", fontSize: 13 }}>
          Nothing learned yet. Chat about what you're looking for — budget, brands,
          must-have features — and it will show up here.
        </div>
      )}

      {budgets.length > 0 && (
        <div>
          <SectionTitle>Budgets</SectionTitle>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {budgets.map(([category, budget]) => (
              <Chip key={category} label={budgetLabel(category, budget)} tone="neutral"
                    onRemove={() => clear("budget", category)} />
            ))}
          </div>
        </div>
      )}

      {excluded.length > 0 && (
        <div>
          <SectionTitle>Never show</SectionTitle>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {excluded.map(([brand]) => (
              <Chip key={brand} label={titleCase(brand)} tone="excluded"
                    onRemove={() => clear("brands", brand)} />
            ))}
          </div>
        </div>
      )}

      {(liked.length > 0 || disliked.length > 0) && (
        <div>
          <SectionTitle>Brands</SectionTitle>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {liked.map(([brand]) => (
              <Chip key={brand} label={titleCase(brand)} tone="positive"
                    onRemove={() => clear("brands", brand)} />
            ))}
            {disliked.map(([brand]) => (
              <Chip key={brand} label={`Not ${titleCase(brand)}`} tone="negative"
                    onRemove={() => clear("brands", brand)} />
            ))}
          </div>
        </div>
      )}

      {categories.length > 0 && (
        <div>
          <SectionTitle>Categories</SectionTitle>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {categories.map(([category, a]) => (
              <Chip key={category} label={titleCase(category)}
                    tone={a.score > 0 ? "positive" : "negative"}
                    onRemove={() => clear("categories", category)} />
            ))}
          </div>
        </div>
      )}

      {features.length > 0 && (
        <div>
          <SectionTitle>Features you care about</SectionTitle>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {features.map(([feature]) => (
              <Chip key={feature} label={titleCase(feature)} tone="positive"
                    onRemove={() => clear("features", feature)} />
            ))}
          </div>
        </div>
      )}

      {attributes.length > 0 && (
        <div>
          <SectionTitle>Specs you prefer</SectionTitle>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {attributes.map(([name, constraint]) => (
              <Chip key={name} label={attributeLabel(name, constraint)} tone="neutral"
                    onRemove={() => clear("attributes", name)} />
            ))}
          </div>
        </div>
      )}

      {rejected.length > 0 && (
        <div>
          <SectionTitle>Products you passed on</SectionTitle>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {rejected.map(([productId, reason]) => (
              <Chip key={productId} label={reason ? `${productId} (${reason})` : productId}
                    tone="negative" onRemove={() => clear("rejected_products", productId)} />
            ))}
          </div>
        </div>
      )}

      {!isEmpty && (
        <button
          onClick={() => clear("all")}
          style={{
            marginTop: 4, alignSelf: "flex-start", display: "flex", alignItems: "center", gap: 6,
            padding: "8px 14px", borderRadius: 10, border: "1px solid var(--border)",
            background: "none", color: "#d02a20", fontSize: 12, fontWeight: 600, cursor: "pointer",
          }}
        >
          <Trash2 size={13} /> Forget everything
        </button>
      )}
    </div>
  );
}
