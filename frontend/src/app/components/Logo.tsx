interface LogoProps {
  size?: number;
  radius?: number;
}

export function Logo({ size = 32, radius }: LogoProps) {
  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: radius ?? Math.round(size * 0.22),
        background: "#E20074",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        flexShrink: 0,
      }}
    >
      <span
        style={{
          color: "#fff",
          fontWeight: 800,
          // Two glyphs need a smaller face than the old single "T" to stay inside the tile.
          fontSize: size * 0.42,
          letterSpacing: -0.5,
          lineHeight: 1,
          fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
        }}
      >
        AI
      </span>
    </div>
  );
}
