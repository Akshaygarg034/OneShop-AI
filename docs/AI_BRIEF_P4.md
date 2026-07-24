# AI Brief — P4: Seamless + Proof (session · cart · checkout · omnichannel · evals · demo)

> **How to use this file:** paste it into your AI together with
> `backend/app/contracts/models.py`. Tell the AI: *"Conform to these contracts, extend the
> existing stubs, keep their signatures, put heavy imports inside functions."*

## Project context
Trustworthy Telekom shopping assistant. Core principle: **AI generates, deterministic rules
decide.** You make it feel like ONE Telekom across devices, and you PROVE the whole thing
works. "How do you know it works?" is the individual round's top seniority question — you own
the answer.

## Your job
1. Session + cart + checkout (the funnel's end).
2. Omnichannel: the same session across web (OneShop) and the mobile view (OneApp).
3. The eval harness (proof).
4. Demo orchestration.

## Files you own
- `backend/app/session/store.py` — session store + cart operations.
- `backend/app/api/cart.py` — cart & checkout endpoints (done).
- `backend/evals/run_evals.py` — the eval harness.
- `frontend/src/features/cart/Cart.jsx` — cart UI + checkout.
- `frontend/src/oneapp/OneApp.jsx` — the phone-shaped mobile view.

## Contracts you produce / consume
- **Produce:** `Cart`, checkout summary, `Session` (holds history + profile + cart).
- **Consume:** the `ChatResponse` (to persist), catalog (for prices via `get_product`).

## Current state (already working in mock mode)
- In-memory `SessionStore` with add/remove/checkout and subtotal math (done).
- Cart + checkout endpoints (done). Frontend cart + phone-frame view (done).
- Eval harness with 5 grounded cases — run: `cd backend && python -m evals.run_evals`.

## Your tasks
**EXTEND — session**
- Persist conversation history + preference profile per `session_id` (already structured; make
  sure P1's profile updates are saved back).
- (Bonus / "what's next") swap in-memory for Redis to show you understand scale.

**EXTEND — omnichannel demo**
- Make the OneShop → OneApp handoff crisp: same `session_id`, cart + history carry over.
- For a two-window demo, both views use the same session id (see `api/client.js`).

**EXTEND — Smart Cart & Checkout**
- Free-shipping threshold nudges (coordinate the copy with P3), a clean checkout summary
  screen, order confirmation.

**GROW — the eval harness (this is your headline)**
- Add cases as features land: "stays in budget", "refuses out-of-catalog", "clarifies when
  vague", "personalization changes ranking after a rejection", "cart math correct",
  "receipts populated". Print a clear PASS/FAIL summary. Judges love this.

**OWN — the demo**
- Seed a repeatable demo session; script the 5–7 min flow; keep a fallback if something breaks.

## How to mock what you don't have
You consume the `ChatResponse` — already real. Build freely.

## Rules for your AI
- Keep cart math correct and deterministic.
- No secrets/PII in logs; mask anything sensitive (audit-trail hygiene).
- Keep endpoints matching the contracts so the frontend keeps working.

## Your "senior story" (rehearse for the individual round)
*"Omnichannel is really a state-continuity problem: one session id, shared history + profile +
cart, so web and mobile are the same conversation. And I own the proof — the eval harness runs
grounded assertions (never recommends out-of-stock, stays in budget, refuses when it should),
which is how we know it works, not just that it demos."*
Be ready for: *"what breaks at DT scale?"* → in-memory session dies with millions of users →
Redis / distributed store; cart writes need idempotency; checkout needs a real
transaction/queue at 1,500 orders/min.
