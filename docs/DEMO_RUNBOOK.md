# Demo Runbook (P4 owns this)

Companion to [PROJECT_OVERVIEW.md](../PROJECT_OVERVIEW.md) section 12 (demo script).
This is the practical "how we actually run it" version, plus what to do if something breaks.

## 1. Before the demo (once, a few minutes ahead)

```bash
cd backend
uvicorn app.main:app --reload          # terminal 1, http://localhost:8000
python -m evals.run_evals              # should print "ALL GREEN" - if not, fix before demoing
python -m evals.seed_demo              # pre-loads a known "demo" session + cart
```

```bash
cd frontend
npm run dev                            # terminal 2, http://localhost:5173
```

`seed_demo` prints two URLs — have both ready in tabs/windows:
- Web: `http://localhost:5173/?session=demo`
- Mobile view: `http://localhost:5173/?session=demo&channel=mobile`

Both point at the **same session_id**, so whatever the seed script did (and anything
typed live) shows up on both — that's the omnichannel proof.

## 2. The 5–7 min flow

1. **Web, discovery** — type: *"I need a phone under €40/mo, I stream a lot and travel
   in Europe."* → grounded picks + "Why this?" panel.
2. **Trust moment** — ask for something out of budget / out of stock (e.g. the iPhone
   16 Pro at €20/mo) → the deterministic engine keeps it off the list. Point at the
   **receipts panel**: it was retrieved, then rejected by a rule (`over_budget` /
   `out_of_stock`) — that's the proof, even if the reply text doesn't name it (see
   Known limitations below).
3. **Personalization** — say *"I don't want Samsung"* → next recommendation reorders;
   point out the profile now lists Samsung under `rejected`.
4. **Smart cart / NBA** — add a phone to cart → nudge for an accessory / "€X from free
   shipping" (`Cart.subtotal` vs `free_shipping_threshold`).
5. **Omnichannel** — switch to the mobile-view tab already open on `?session=demo` →
   same history, same cart. Finish checkout there.
6. **Close (30s)** — architecture diagram + "AI generates, deterministic rules decide."

## 3. Proof, on demand

If anyone asks "how do you know it works?": run `python -m evals.run_evals` live.
12 grounded cases, grouped as TRUST / CONVERSATION / PERSONALIZATION / CART, exit
code fails the run if anything regresses — this is the answer to that question.

## 4. Fallback if something breaks

- **Backend crashes mid-demo**: restart `uvicorn`, re-run `python -m evals.seed_demo`
  (idempotent — safe to re-run), reload both browser tabs. Takes under 20 seconds.
- **A real API (Grok/Qdrant) is down or a key is missing**: set `MOCK_MODE=true` in
  `backend/.env` and restart — the whole app runs on deterministic mocks, indistinguishable
  in the demo flow.
- **Session persistence (Supabase) is down**: the store falls back to in-memory
  automatically (logs a warning, doesn't crash) — the demo keeps working, you just lose
  cross-restart persistence for that run.
- **Totally stuck**: narrate the architecture diagram from `PROJECT_OVERVIEW.md` section 7
  and walk through one `evals/run_evals.py` case in the code — still demonstrates the
  core idea (AI generates, rules decide) without a live UI.

## 5. Known limitations (say these out loud — they read as judgement, not weakness)

- The trust-moment reply text picks the best *available* option but doesn't yet say
  "I can't offer the iPhone 16 Pro at that price" by name when a specific product is
  asked for and rejected — that needs intent to recognize a *named* product ask
  (P1's `agents/intent.py` + the reply composer in `agents/graph.py`). The receipts
  panel already proves the rejection happened; the copy is a polish item, not a
  trust gap.
- Session persistence defaults to in-memory; Supabase is wired in but optional
  (`SESSION_BACKEND=auto` in `.env` — falls back safely if unset/unreachable).
- Checkout is a mock confirmation (no real payment) — a deliberate 24h-POC cut.
