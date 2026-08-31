// The catalog uses only basic color names, so the palette stays small and scannable.
const COLOR_HEX: Record<string, string> = {
  black: "#1A1A1A",
  white: "#FFFFFF",
  gray: "#8E8E93",
  blue: "#2D6BD8",
  red: "#D33A2F",
  green: "#3E9C6E",
  yellow: "#F2D24B",
  pink: "#F19CBB",
  purple: "#7D4DB8",
  brown: "#8B6A50",
};

function isLight(hex: string): boolean {
  const n = parseInt(hex.slice(1), 16);
  const brightness = ((n >> 16) & 255) * 0.299 + ((n >> 8) & 255) * 0.587 + (n & 255) * 0.114;
  return brightness > 200;
}

function titleCase(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/** Available-color swatches for a product card. Hover a dot for its name —
 * a custom CSS tooltip (~0.15s), since native `title` tooltips take ~1s. */
export function ColorDots({ colors, size = 12, max = 5 }: { colors: string[]; size?: number; max?: number }) {
  if (!colors.length) return null;
  const shown = colors.slice(0, max);
  const extra = colors.length - shown.length;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 4 }} aria-label={`Colors: ${colors.join(", ")}`}>
      {shown.map((color) => {
        const hex = COLOR_HEX[color.toLowerCase()] ?? "#B0B0B0";
        return (
          <span
            key={color}
            className="color-dot"
            data-color={titleCase(color)}
            style={{
              width: size,
              height: size,
              borderRadius: "50%",
              background: hex,
              border: isLight(hex) ? "1px solid rgba(0,0,0,0.25)" : "1px solid rgba(0,0,0,0.08)",
              flexShrink: 0,
              position: "relative",
            }}
          />
        );
      })}
      {extra > 0 && (
        <span
          className="color-dot"
          data-color={colors.slice(max).map(titleCase).join(", ")}
          style={{ fontSize: size - 3, color: "var(--muted-foreground)", fontWeight: 600, position: "relative" }}
        >
          +{extra}
        </span>
      )}
      <style>{`
        .color-dot:hover::after {
          content: attr(data-color);
          position: absolute;
          bottom: calc(100% + 5px);
          left: 50%;
          transform: translateX(-50%);
          background: rgba(20, 20, 24, 0.92);
          color: #fff;
          font-size: 10px;
          font-weight: 600;
          line-height: 1;
          padding: 4px 7px;
          border-radius: 5px;
          white-space: nowrap;
          pointer-events: none;
          z-index: 50;
          opacity: 0;
          animation: color-tip-in 0.12s ease 0.15s forwards;
        }
        @keyframes color-tip-in {
          to { opacity: 1; }
        }
      `}</style>
    </div>
  );
}
