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
          fontSize: size * 0.56,
          lineHeight: 1,
          fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
        }}
      >
        T
      </span>
    </div>
  );
}
