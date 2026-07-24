# Backend — Telekom Smart Shopping Assistant

FastAPI + LangGraph + OpenAI + Qdrant. Runs on **mock data** out of the box (no keys).

## Run (mock mode)
```bash
python -m venv .venv && source .venv/Scripts/activate     # Windows Git Bash
pip install fastapi "uvicorn[standard]" pydantic python-dotenv
cp .env.example .env            # MOCK_MODE=true
uvicorn app.main:app --reload   # http://localhost:8000/docs
```

## Run the evals
```bash
python -m evals.run_evals
```

## Going real

Everything below degrades gracefully — if a service is down or unconfigured, the
app falls back (Postgres → JSON catalog, Qdrant → keyword search, Supabase → memory),
so the demo never hard-fails.

**1. Auth + catalog in Supabase (Postgres over REST):**
```bash
pip install -r requirements.txt
# In .env set SUPABASE_URL (https://<ref>.supabase.co) and SUPABASE_KEY
# (a service_role JWT or an sb_secret_... key from Settings -> API).
# We use the REST API, NOT a direct psycopg2 connection — the direct
# db.<ref>.supabase.co host is IPv6-only and usually won't resolve.

# Run these once in the Supabase SQL editor:
#   app/auth/supabase_schema.sql          (users)
#   app/retrieval/catalog_schema.sql      (catalog_products — prices/stock)
#   app/session/supabase_schema.sql       (sessions — optional persistence)

python -m app.retrieval.seed_catalog      # load prices/stock into catalog_products
```

**2. Semantic retrieval (RAG) with Qdrant:**
```bash
docker compose up -d qdrant               # from repo root
python -m app.rag.ingestion               # embed data/catalog.json -> Qdrant (without image URLs)
# set RAG_ENABLED=true in .env    (retrieve() now does vector search)
python -m app.rag.retriever               # optional: manual search REPL
```

**3. OpenAI generation (P1/P3):** set `OPENAI_API_KEY` and flip `MOCK_MODE=false`.

### Catalog sync (catalog.json is the source of truth)
- `data/catalog.json` → upserted into `catalog_products` (including image URLs).
- The same file is embedded into Qdrant with `image_url` removed.
- Run `python update_catalog.py` after editing the catalog.
- Retrieval finds candidate ids by meaning in Qdrant, then reads authoritative
  prices/stock from Postgres — "AI generates, deterministic rules decide."

## Layout (folder = owner)
```
app/
  contracts/models.py   - data shapes (single source of truth)
  agents/               - intent, profile, graph orchestrator
  retrieval/            - catalog loader (Postgres/JSON) + keyword/semantic retrieve
  rag/                  - Qdrant ingestion + semantic search (importable modules)
  engine/               - deterministic eligibility engine
  recommend/            - ranking, "why", next-best-action
  session/              - session store, cart, checkout
  auth/                 - user accounts (Supabase users table) + tokens
  api/                  - chat.py, cart.py, catalog.py, auth.py
data/
  catalog.json            - single source for Postgres + Qdrant sync
evals/run_evals.py      - proof harness (offline; some cases skip if Qdrant is down)
```

Switches in `.env` / `app/config.py`:
- `MOCK_MODE`        - OpenAI generation on/off (intent, "why")
- `RAG_ENABLED`      - semantic Qdrant retrieval vs keyword matching
- `CATALOG_BACKEND`  - `auto` (Postgres+fallback) or `json`
- `SESSION_BACKEND`  - `auto`/`memory`/`supabase`

See [`../START_HERE.md`](../START_HERE.md).
