// Nudges (Next-Best-Action) + trust receipts. Owned by P3.
// The per-recommendation "why" text lives on the ProductCard; this panel shows the
// funnel nudges and the "keep receipts" transparency that proves grounding.
import React from "react";

export default function WhyPanel({ nba, receipts }) {
  const hasNudges = nba && nba.length > 0;
  const hasReceipts = receipts && receipts.retrieved_ids && receipts.retrieved_ids.length > 0;
  if (!hasNudges && !hasReceipts) return null;

  return (
    <div className="panel">
      <h3>Smart suggestions</h3>
      {hasNudges
        ? nba.map((n, i) => <div key={i} className="nudge">✨ {n}</div>)
        : <div className="receipts">No nudges right now.</div>}

      {hasReceipts && (
        <div className="receipts" style={{ marginTop: 12 }}>
          <strong>Why you can trust this</strong>
          <div>Searched: {receipts.retrieved_ids.length} products</div>
          <div>Rules applied: {receipts.rules_fired.map((r, i) => <code key={i}>{r}</code>)}</div>
          <div>Shown only: {receipts.shown_ids.length} that passed every rule</div>
        </div>
      )}
    </div>
  );
}
