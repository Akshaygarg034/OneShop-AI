import { useState, type FormEvent } from "react";
import { X, Sparkles } from "lucide-react";
import { useAuth } from "../auth/AuthContext";

type Mode = "login" | "register";

interface AuthModalProps {
  open: boolean;
  onClose: () => void;
}

interface FieldProps {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  placeholder?: string;
  required?: boolean;
}

function Field({ label, value, onChange, type = "text", placeholder, required }: FieldProps) {
  return (
    <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <span style={{ fontSize: 11.5, fontWeight: 600, color: "var(--muted-foreground)" }}>{label}</span>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        required={required}
        style={{
          background: "var(--input-background)",
          border: "1.5px solid rgba(var(--primary-rgb),0.25)",
          borderRadius: 12,
          padding: "10px 14px",
          fontSize: 13,
          color: "var(--foreground)",
          outline: "none",
        }}
        onFocus={(e) => (e.target.style.borderColor = "var(--primary)")}
        onBlur={(e) => (e.target.style.borderColor = "rgba(var(--primary-rgb),0.25)")}
      />
    </label>
  );
}

export function AuthModal({ open, onClose }: AuthModalProps) {
  const { login, register } = useAuth();
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (!open) return null;

  const reset = () => {
    setEmail("");
    setPassword("");
    setName("");
    setError("");
    setSubmitting(false);
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  const switchMode = (m: Mode) => {
    setMode(m);
    setError("");
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      if (mode === "login") {
        await login({ email, password });
      } else {
        await register({ email, password, name });
      }
      handleClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
      setSubmitting(false);
    }
  };

  return (
    <div
      role="presentation"
      onClick={handleClose}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.5)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
        padding: 16,
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={mode === "login" ? "Sign in" : "Create account"}
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "min(400px, 100%)",
          background: "var(--card)",
          border: "1px solid var(--border)",
          borderRadius: 20,
          boxShadow: "0 16px 48px rgba(0,0,0,0.25)",
          padding: 28,
        }}
      >
        <div className="flex items-center justify-between" style={{ marginBottom: 20 }}>
          <div className="flex items-center gap-2">
            <div
              style={{
                width: 32,
                height: 32,
                borderRadius: "50%",
                background: "linear-gradient(135deg, var(--primary), #7B61FF)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
              }}
            >
              <Sparkles size={15} style={{ color: "#fff" }} />
            </div>
            <span style={{ fontSize: 16, fontWeight: 800, color: "var(--foreground)" }}>
              {mode === "login" ? "Welcome back" : "Create your account"}
            </span>
          </div>
          <button
            onClick={handleClose}
            aria-label="Close"
            style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted-foreground)", padding: 4, display: "flex" }}
          >
            <X size={18} />
          </button>
        </div>

        <div style={{ display: "flex", background: "var(--muted)", borderRadius: 50, padding: 3, marginBottom: 20 }}>
          {(["login", "register"] as Mode[]).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => switchMode(m)}
              style={{
                flex: 1,
                padding: "8px 0",
                borderRadius: 50,
                border: "none",
                cursor: "pointer",
                background: mode === m ? "var(--primary)" : "transparent",
                color: mode === m ? "#fff" : "var(--foreground)",
                fontSize: 12.5,
                fontWeight: 700,
                transition: "background 0.15s ease, color 0.15s ease",
              }}
            >
              {m === "login" ? "Sign in" : "Sign up"}
            </button>
          ))}
        </div>

        <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {mode === "register" && (
            <Field label="Name" value={name} onChange={setName} placeholder="Jamie Müller" />
          )}
          <Field label="Email" type="email" value={email} onChange={setEmail} placeholder="you@example.com" required />
          <Field
            label="Password"
            type="password"
            value={password}
            onChange={setPassword}
            placeholder={mode === "register" ? "At least 8 characters" : "••••••••"}
            required
          />

          {error && <p style={{ fontSize: 12, color: "var(--destructive)", margin: 0 }}>{error}</p>}

          <button
            type="submit"
            disabled={submitting}
            style={{
              marginTop: 4,
              padding: "11px 0",
              background: "var(--primary)",
              border: "none",
              borderRadius: 50,
              color: "#fff",
              fontSize: 13.5,
              fontWeight: 700,
              cursor: submitting ? "default" : "pointer",
              opacity: submitting ? 0.6 : 1,
            }}
          >
            {submitting ? "Please wait..." : mode === "login" ? "Sign in" : "Create account"}
          </button>
        </form>

        <p style={{ fontSize: 11.5, color: "var(--muted-foreground)", textAlign: "center", marginTop: 16 }}>
          {mode === "login" ? "New to OneShop? " : "Already have an account? "}
          <button
            type="button"
            onClick={() => switchMode(mode === "login" ? "register" : "login")}
            style={{ background: "none", border: "none", padding: 0, color: "var(--primary)", fontWeight: 700, cursor: "pointer", fontSize: 11.5 }}
          >
            {mode === "login" ? "Create an account" : "Sign in"}
          </button>
        </p>
      </div>
    </div>
  );
}
