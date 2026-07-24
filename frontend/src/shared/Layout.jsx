// Shared app shell: header + channel toggle (web / mobile). SHARED (hour 0).
import React from "react";

export default function Layout({ channel, setChannel, children }) {
  return (
    <div>
      <div className="header">
        <h1>Telekom &mdash; Smart Shopping Assistant</h1>
        <div className="channel-toggle">
          <button
            className={channel === "web" ? "active" : ""}
            onClick={() => setChannel("web")}
          >
            OneShop (Web)
          </button>
          <button
            className={channel === "mobile" ? "active" : ""}
            onClick={() => setChannel("mobile")}
          >
            OneApp (Mobile)
          </button>
        </div>
      </div>
      {children}
    </div>
  );
}
