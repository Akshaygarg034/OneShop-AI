# Smart Shopping Assistant

An AI-powered consumer intelligence engine that personalizes shopping across web and mobile:
conversational shopping assistance, personalized recommendations, contextual next-best actions,
intelligent cart optimization, and durable cross-channel identity.

**Stack:** FastAPI · LangGraph · OpenAI · Qdrant (vectors) · Supabase/Postgres (data) · React + Vite

```
Smart-Shopping-Assistant/
├── backend/     # FastAPI + LangGraph agent (see backend/README.md)
├── frontend/    # React storefront + chat UI
└── docker-compose.yml
```

## How it works

**AI generates, deterministic rules decide.** One LLM call per turn understands the message —
intent, hard constraints (budget/brand/color/specs), and durable preference changes. Retrieval
pushes those constraints into Qdrant as payload filters, a deterministic eligibility engine
re-verifies every candidate against live catalog data, and a transparent scoring engine ranks
what's left. The LLM phrases the reply (streamed over SSE) but can never recommend a product
the rules rejected.

The agent is a LangGraph `StateGraph`:

```
load_context → understand ─┬→ retrieve → evaluate → rank → respond (streaming) ─┐
                           ├→ greeting / off-topic / clarify / cart-question ───┤
                           └→ preference-only acknowledgement ──────────────────┴→ persist
```

**Preference learning** combines two signal sources, persisted per user:
- *Conversational*: "my budget is 500–800", "never show me Apple", "I need a great camera",
  "actually Apple is fine now" — extracted as structured deltas with hard exclusions,
  soft affinities, recency decay, and retraction.
- *Behavioral*: add-to-cart, remove, and purchase events adjust brand/category/feature
  affinities; purchases set an inferred budget prior (ranking-only, never a hard filter).

**Conversation memory at scale**: recent messages verbatim + a rolling summary per
conversation + semantic recall (RAG) over all past messages in Qdrant — prompts stay
bounded no matter how long the history grows.

Amounts in any currency (Rs, ₹, $, €) are read as EUR — the catalog's currency — and the
assistant says so.

## Quick start

Prerequisites: Python 3.11+, Node 20+, a Supabase project, a Qdrant instance (cloud or
`docker compose up qdrant`), and an OpenAI API key.

**1. Backend**

```bash
cd backend
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # fill in keys; AUTH_SECRET: python -c "import secrets; print(secrets.token_urlsafe(48))"
python update_catalog.py    # seed Supabase + Qdrant with data/catalog.json (50 products)
uvicorn app.main:app --reload
# http://127.0.0.1:8000/docs · /health · /ready
```

Database tables and Qdrant collections are created automatically at startup when
`SUPABASE_DB_URL` (direct Postgres connection string) is set in `.env`. Without it,
run `backend/db/schema.sql` once in the Supabase SQL editor instead — the server
tells you if the tables are missing.

**2. Frontend**

```bash
cd frontend
npm install
npm run dev                 # http://localhost:5173
```

**Verify**

```bash
cd backend
python -m pytest tests      # unit + API contract tests (no network needed)
python -m evals.run_evals   # behavioral evals against the real LLM pipeline
cd ../frontend && npm run typecheck
```

## Docker

```bash
docker compose up --build   # Qdrant + backend on :8000 (Supabase stays cloud)
```

## Security model

- JWT access tokens (PyJWT/HS256), Argon2id password hashing (legacy hashes re-hash on login).
- Chat requires a signed-in account by default (`REQUIRE_LOGIN_FOR_CHAT=true`); guests can
  still browse and manage a cart, which merges into their account on login. Set the flag to
  `false` for guest-first chat (the Amazon-style pattern).
- Every session-scoped endpoint — chat, cart, history, profile — verifies ownership:
  guest sessions are unguessable capabilities; account sessions require a matching bearer token.
- Rate limiting on auth and LLM-spending endpoints; CORS origin allowlist; RLS enabled on all
  tables (service-role key only, server-side).
