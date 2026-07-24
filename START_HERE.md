# START HERE — read this in the first 10 minutes

Welcome. This repo is a **working skeleton** for our Telekom Smart Shopping Assistant.
It already runs end-to-end on **mock data** — your job is to replace your slice's mock with
real code, without breaking anyone else.

## 1. What we're building (30 seconds)
An AI shopping assistant that recommends **real, in-stock, eligible** Telekom products,
explains **why** each fits you, learns your preferences, nudges you to checkout, and works
across web + mobile. Core principle: **AI generates, deterministic rules decide** (so it
never hallucinates a product). Full detail in [`PROJECT_OVERVIEW.md`](PROJECT_OVERVIEW.md).

## 2. Get it running (mock mode, no keys)
See [`README.md`](README.md) → Quick start. You should have the backend on `:8000` and the
frontend on `:5173` within 10 minutes. Type a message like *"phone under €40 with a good
camera, I travel in Europe"* — you'll get grounded recommendations. **That's checkpoint C1.**

## 3. Who owns what
| You are | Read your brief | You own these folders |
|---|---|---|
| **P1 — Brain** | [`docs/AI_BRIEF_P1.md`](docs/AI_BRIEF_P1.md) | `backend/app/agents/`, `backend/app/api/chat.py`, `frontend/src/features/chat/` |
| **P2 — Truth** | [`docs/AI_BRIEF_P2.md`](docs/AI_BRIEF_P2.md) | `backend/app/retrieval/`, `backend/app/engine/`, `backend/data/`, `frontend/src/features/product-card/` |
| **P3 — Persuasion** | [`docs/AI_BRIEF_P3.md`](docs/AI_BRIEF_P3.md) | `backend/app/recommend/`, `frontend/src/features/why-panel/` |
| **P4 — Seamless+Proof** | [`docs/AI_BRIEF_P4.md`](docs/AI_BRIEF_P4.md) | `backend/app/session/`, `backend/app/api/cart.py`, `backend/evals/`, `frontend/src/features/cart/`, `frontend/src/oneapp/` |

**Only edit your own folders.** The one shared file, `backend/app/contracts/models.py`, changes
only by team agreement (announce it, everyone pulls).

## 4. How to use YOUR AI tool (Cursor / Copilot / Claude / etc.)
At the start of each session, paste TWO things into your AI:
1. **Your brief** — `docs/AI_BRIEF_P<n>.md`
2. **The contracts** — `backend/app/contracts/models.py`

Then tell it: *"All data must conform to these contracts. Extend the existing stub functions;
keep their signatures. Put heavy imports (qdrant, langchain, sentence-transformers) inside
functions, not at module top, so mock mode keeps working."*

**Always verify what the AI writes** — read it, run it, check it against the contract. This is
literally scored in the individual round ("do they verify AI output or just paste?").

## 5. The one rule that keeps us unblocked
> **Depend on the *contract*, never on someone's *implementation*.**
If you need another slice that isn't ready, use its mock and keep going. Nobody waits.

## 6. Git
- Your own branch: `feat/p1-...`, `feat/p2-...`, etc. Commit under **your own name**.
- `main` must always run. Merge at the checkpoints in [`TEAM_TASKS_AND_WORKFLOW.md`](TEAM_TASKS_AND_WORKFLOW.md).

## 7. Before the demo
Each person rehearses their **"senior story"** (bottom of your brief) out loud — that's the
individual round, where offers are decided.
