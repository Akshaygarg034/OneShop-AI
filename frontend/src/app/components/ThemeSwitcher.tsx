import { Sun, Moon } from "lucide-react";
import { useTheme } from "../theme/ThemeProvider";

export function ThemeSwitcher() {
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === "dark";

  return (
    <button
      onClick={toggleTheme}
      title={isDark ? "Switch to light mode" : "Switch to dark mode"}
      style={{
        position: "relative",
        display: "flex",
        alignItems: "center",
        width: 44,
        height: 24,
        borderRadius: 20,
        border: "1px solid var(--border)",
        background: "var(--muted)",
        cursor: "pointer",
        flexShrink: 0,
        padding: 0,
      }}
    >
      <span
        style={{
          position: "absolute",
          top: 2,
          left: isDark ? 22 : 2,
          width: 18,
          height: 18,
          borderRadius: "50%",
          background: "var(--primary)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          transition: "left 0.2s ease",
        }}
      >
        {isDark
          ? <Moon size={10} style={{ color: "#fff" }} />
          : <Sun size={10} style={{ color: "#fff" }} />
        }
      </span>
    </button>
  );
}
