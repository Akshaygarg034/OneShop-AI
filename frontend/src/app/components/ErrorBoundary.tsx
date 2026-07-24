import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

interface Props {
  children: ReactNode;
  /** Short label for what crashed, shown in the fallback (e.g. "product catalog"). */
  label: string;
}

interface State {
  error: Error | null;
}

/**
 * Contains a render crash to the section that threw it instead of blanking
 * the whole storefront - e.g. a malformed backend payload in the product
 * grid shouldn't take the chat widget or checkout down with it. Logs to the
 * console for diagnosis; "Try again" just re-mounts the subtree.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(`[${this.props.label}] crashed:`, error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: 12,
            padding: "60px 24px",
            textAlign: "center",
            color: "var(--foreground)",
          }}
        >
          <AlertTriangle size={28} style={{ color: "#FF6B35" }} />
          <div>
            <p style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>
              Something went wrong loading the {this.props.label}.
            </p>
            <p style={{ fontSize: 12, color: "var(--muted-foreground)" }}>
              The rest of the page still works - you can try this section again.
            </p>
          </div>
          <button
            onClick={() => this.setState({ error: null })}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              padding: "8px 16px",
              borderRadius: 8,
              border: "1px solid var(--border)",
              background: "none",
              color: "var(--foreground)",
              fontSize: 12,
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            <RefreshCw size={13} /> Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
