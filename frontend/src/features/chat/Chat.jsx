// Chat UI. Owned by P1.
// Renders the conversation and an input box. Calls onSend(message) from the parent.
import React, { useState } from "react";

export default function Chat({ messages, onSend, busy }) {
  const [text, setText] = useState("");

  const submit = (e) => {
    e.preventDefault();
    const t = text.trim();
    if (!t || busy) return;
    onSend(t);
    setText("");
  };

  return (
    <div className="panel">
      <h3>Chat</h3>
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="msg assistant">
            Hi! Tell me what you're looking for &mdash; e.g. "a phone under &euro;40/mo
            with a great camera, I travel in Europe".
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>{m.content}</div>
        ))}
        {busy && <div className="msg assistant">…thinking</div>}
      </div>
      <form className="chat-input" onSubmit={submit}>
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Type what you need…"
        />
        <button type="submit" disabled={busy}>Send</button>
      </form>
    </div>
  );
}
