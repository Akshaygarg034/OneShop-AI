# AI Brief — P2: The Truth (RAG retrieval · deterministic eligibility engine · catalog)

> **How to use this file:** paste it into your AI together with
> `backend/app/contracts/models.py`. Tell the AI: *"Conform to these contracts, extend the
> existing stubs, keep their signatures, put heavy imports inside functions."*

## Project context
Trustworthy Telekom shopping assistant. Core principle: **AI generates, deterministic rules
decide.** You build the "decide" half — the source of truth. This is the most senior slice:
the reason the assistant can be trusted at all.
Pipeline: intent (P1) → **retrieve (you)** → **eligibility (you)** → recommend (P3) → response.

## Your job
1. Make product search real (semantic RAG with Qdrant).
2. Own the deterministic eligibility engine — the rules that decide what's offerable.
3. Own the catalog data.

## Files you own
- `backend/data/catalog.json` — the product catalog (grow it to ~100–150 items).
- `backend/app/retrieval/catalog.py` — loader (done).
- `backend/app/retrieval/retriever.py` — `retrieve(intent) -> list[Product]`.
- `backend/app/engine/eligibility.py` — `filter_eligible(products, intent) -> list[EligibleProduct]`.
- `backend/app/api/catalog.py` — read endpoint (done).
- `frontend/src/features/product-card/ProductCard.jsx` — card with stock/eligibility badge.

## Contracts you produce / consume
- **Produce:** `Product[]` (candidates), `EligibleProduct[]` (with `eligible`, `reasons`, `failed_rules`).
- **Consume:** `Intent` from P1.

## Current state (already working in mock mode)
- `retriever.py` does keyword matching over the catalog (mock).
- `eligibility.py` is ALREADY REAL and deterministic (in-stock + budget rules). Extend it.
- Seed `catalog.json` has 10 items including an out-of-stock iPhone (for the trust demo).

## Your tasks
**DATA (do first — everyone needs it):** expand `catalog.json` to ~100–150 realistic items
(phones, MagentaMobil plans, accessories, bundles) with good `features`, `price_monthly`,
`stock`, `compatible_plans`. Keep 1–2 items out of stock for the demo.

**REAL — retrieval** (`retrieval/retriever.py::_retrieve_real`)
- Embed each product's text (name + description + features) with `EMBED_MODEL`
  (`sentence-transformers`, import inside the function).
- Upsert vectors + product id into Qdrant (`QDRANT_URL`, `QDRANT_COLLECTION`).
- On query: build a query string from `intent`, embed it, search top-k, map ids → `Product`
  via `catalog.get_product`. Keep the SAME signature as the mock.
- Add a one-off `ingest()` script/function to build the collection.

**REAL — eligibility (extend the engine):** add rules — plan/device compatibility,
feature must-haves, category filter. Every rule must be a pure function (same input → same
output). Record each pass/fail in `reasons` / `failed_rules`.

**POLISH**
- Metadata filtering in Qdrant (e.g. only `type=phone`).
- A "flip to out-of-stock" toggle for the live trust demo.
- Frontend: clear in-stock / out-of-stock badge on the card.

## How to mock what you don't have
You depend only on `Intent` (P1) — already real. Build freely.

## Rules for your AI
- **No LLM calls in `eligibility.py`, ever.** It must be deterministic and reproducible.
- Keep `MOCK_MODE` working: real Qdrant code behind `_retrieve_real`; import qdrant/
  sentence-transformers inside functions so mock mode needs neither.
- Volatile facts (stock/price) are checked live here — never rely on the vector index for them.

## Your "senior story" (rehearse for the individual round)
*"The LLM can't hallucinate a product because it never decides what's offerable — my engine
does, deterministically. Retrieval finds candidates by meaning (Qdrant + embeddings); the
engine filters by live truth (stock, budget, compatibility). Same state in → same verdict out,
every time. Stock is never in the vector index — it's a live check — so we can't recommend
something out of stock."*
Be ready for: *"how do you keep it fresh at scale?"* → re-embed on product-change events;
cache hot queries; stock stays a live lookup.
