import { Facebook, Instagram, Linkedin, Twitter } from "lucide-react";
import { Logo } from "./Logo";

const socialIcons = [Facebook, Instagram, Linkedin, Twitter];
const policyLinks = ["Privacy Policy", "Terms of Service", "Imprint", "Cookie Settings"];

export function SiteFooter() {
  return (
    <footer style={{ background: "#111111", padding: "40px 32px 24px", flexShrink: 0 }}>
      <div style={{ maxWidth: 1280, margin: "0 auto" }}>
        <div className="flex items-center justify-between" style={{ marginBottom: 28, flexWrap: "wrap", gap: 16 }}>
          <div className="flex items-center gap-2">
            <Logo size={30} />
            <span style={{ color: "#fff", fontWeight: 700, fontSize: 14 }}>OneShop</span>
          </div>
          <div className="flex items-center" style={{ gap: 10 }}>
            {socialIcons.map((Icon, i) => (
              <div
                key={i}
                style={{
                  width: 32, height: 32, borderRadius: "50%", background: "#E20074",
                  display: "flex", alignItems: "center", justifyContent: "center",
                }}
              >
                <Icon size={14} style={{ color: "#fff" }} />
              </div>
            ))}
          </div>
        </div>
        <div style={{ borderTop: "1px solid rgba(255,255,255,0.1)", paddingTop: 18 }}>
          <div className="flex items-center justify-between" style={{ flexWrap: "wrap", gap: 10 }}>
            <div className="flex items-center" style={{ gap: 18 }}>
              {policyLinks.map((label) => (
                <span key={label} style={{ color: "#B3B3B3", fontSize: 11.5 }}>{label}</span>
              ))}
            </div>
            <span style={{ color: "#6B6B6B", fontSize: 11 }}>© {new Date().getFullYear()} OneShop. All rights reserved.</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
