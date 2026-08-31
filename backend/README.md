# Backend — FastAPI + LangGraph agent

## Layout

```
app/
├── main.py               # app factory, CORS, rate limiting, /health + /ready probes
├── config.py             # pydantic-settings; fails fast on missing/weak config
├── clients.py            # shared async OpenAI / Qdrant / Supabase clients
├── agents/
│   ├── graph.py          # the LangGraph StateGraph + run_turn()
│   ├── understand.py     # one structured LLM call: intent + filters + preference deltas
│   ├── respond.py        # streaming reply composer + deterministic templates
│   └── schemas.py        # Understanding (structured-output schema)
├── preferences/          # models, learning engine (deltas/events/decay/merge), store
├── conversations/        # per-message persistence, rolling summaries, semantic recall
├── retrieval/            # catalog TTL cache, Qdrant ingestion, hybrid retriever
├── engine/eligibility.py # deterministic rules — the source of truth for offerability
├── recommend/            # signal-based ranking, diversification, next-best actions
├── session/store.py      # cart with optimistic-concurrency writes, checkout, guest merge
├── auth/                 # Argon2 + JWT, user store, session-ownership checks
├── api/                  # chat (JSON + SSE), cart, catalog, auth, profile routers
├── contracts/models.py   # shared Pydantic contracts (Product, ChatResponse, ...)
├── bootstrap.py          # auto-creates DB tables + Qdrant collections at startup
└── observability.py      # JSON logs + request-id middleware
db/schema.sql              # idempotent Supabase schema (auto-applied via SUPABASE_DB_URL)
data/catalog.json          # 50-product seed catalog with rich per-category attributes
update_catalog.py          # sync catalog.json → Supabase + Qdrant (idempotent)
evals/run_evals.py         # behavioral evals against the real LLM pipeline
tests/                     # unit + API contract tests (memory backend, LLM mocked)
```

## Configuration

Copy `.env.example` → `.env`. Required: `OPENAI_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`,
`QDRANT_URL` (+ `QDRANT_API_KEY` for cloud), and a ≥32-char `AUTH_SECRET`.
`STORAGE_BACKEND=memory` runs everything in-process (tests/offline dev) — carts,
preferences, and conversations then don't survive a restart.

Set `SUPABASE_DB_URL` (dashboard → Settings → Database → connection string) and the
server applies `db/schema.sql` on every startup — fully idempotent and non-destructive:
missing tables are created, missing columns are added, existing data is never touched.
The REST API can't run DDL, so without this the schema must be applied manually once.

## Chat API

- `POST /chat` — full JSON response: `{reply_text, recommendations, products, nba, cart, receipts, conversation_id}`.
  `products` embeds the recommended products in full, so clients need no follow-up catalog fetch.
- `POST /chat/stream` — SSE: `token` (reply deltas) → `recommendations` (+ full products) → `nba` → `done`.
- `GET /chat/history`, `GET /chat/conversations`, `DELETE /chat/conversations/{id}`.

All session-scoped endpoints take `session_id` and, for logged-in sessions
(`session_id == user_id`), require `Authorization: Bearer <jwt>`.

## Catalog

`data/catalog.json` is the single source. Each product carries practical commerce metadata —
price/original price/discount, rating + review count, colors, stock, warranty, features, and a
per-category `attributes` object (e.g. smartphones: `ram_gb`, `storage_gb`, `display_inch`,
`battery_mah`, `main_camera_mp`, `chipset`, `os`, `connectivity`, …).

`python update_catalog.py` validates and upserts to Supabase, then re-embeds into Qdrant with
deterministic point IDs (re-runs update in place; removed products are pruned).
Prices/stock are never embedded — they live in Postgres and are re-checked on every turn;
the Qdrant payload carries filterable copies (brand, category, price, stock) refreshed on
each sync so constraints can be pushed into the vector search.

## Testing

```bash
python -m pytest tests      # fast, hermetic (memory backend, LLM mocked)
python -m evals.run_evals   # real OpenAI + Qdrant: budget ranges, currency, exclusions,
                            # attribute/color filters, behavioral signals, scope guards
```
