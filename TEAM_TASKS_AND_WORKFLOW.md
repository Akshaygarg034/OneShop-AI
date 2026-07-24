# Team Task Division & Collaboration Workflow

> Companion to [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md).
> This file answers two questions: **(1) exactly who builds what, and (2) how 4 people — each using their own AI coding tools — work in parallel without blocking or colliding.**

---

## 0. The one idea that makes parallel work possible: **Contract-first + Mock-first**

The reason 4 people usually *can't* work independently is that everyone's code depends on everyone else's code. We break that dependency with two rules:

1. **Contract-first** — before writing real logic, we agree on the exact **data shapes** (JSON / Pydantic models) that pass between each person's module. These live in ONE shared file: `backend/app/contracts/models.py`. Nobody invents their own shapes.
2. **Mock-first** — by **Hour 2, the whole app runs end-to-end on fake data.** Every module returns hardcoded, contract-shaped mock data. The pipeline works. *Then* each person replaces their own mock with the real implementation — **in isolation, without waiting for anyone.**

After Hour 2, you almost never block each other. P3 can build ranking against a hardcoded list of "eligible products" long before P2's real Qdrant retrieval exists. When P2 is ready, P3's code doesn't change — the shape is identical.

> **Golden rule:** You depend on the *contract*, never on someone's *implementation*.

---

## 1. Repo structure & folder ownership (no two people edit the same files)

```
telekom-assistant/
├── docker-compose.yml              # Qdrant + backend (SHARED, hour 0)
├── PROJECT_OVERVIEW.md
├── TEAM_TASKS_AND_WORKFLOW.md
├── backend/
│   ├── requirements.txt
│   └── app/
│       ├── main.py                 # FastAPI entry (SHARED, thin, rarely touched)
│       ├── contracts/
│       │   └── models.py           # SHARED — the single source of truth for data shapes
│       ├── agents/                 # P1 — LangGraph graph, intent, preference profile
│       ├── retrieval/              # P2 — Qdrant client, embeddings, catalog ingest
│       ├── engine/                 # P2 — deterministic eligibility rules
│       ├── recommend/              # P3 — ranking, explanation, NBA, guardrails
│       ├── session/                # P4 — session store, cart, checkout
│       └── api/
│           ├── chat.py             # P1 wires the pipeline into one endpoint
│           └── cart.py             # P4 — cart & checkout endpoints
│   └── data/
│       └── catalog.json            # P2 (generated hour 0, SHARED read-only)
│   └── evals/                      # P4 — the eval harness
└── frontend/
    └── src/
        ├── shared/                 # SHARED shell — layout, chat window base, product card base
        ├── api/                    # SHARED — thin API client
        ├── oneshop/                # web page (SHARED shell assembles the features)
        ├── oneapp/                 # P4 — mobile-shaped view
        └── features/
            ├── chat/               # P1 — chat message list + input
            ├── product-card/       # P2 — product card w/ stock & eligibility badges
            ├── why-panel/          # P3 — "Why this?" + nudge banners
            └── cart/               # P4 — cart UI + checkout flow
```

**Ownership map (each person's folders — they own these, others don't touch):**

| Person | Backend folders | Frontend folders |
|---|---|---|
| **P1 — Brain** | `agents/`, `api/chat.py` | `features/chat/` |
| **P2 — Truth** | `retrieval/`, `engine/`, `data/catalog.json` | `features/product-card/` |
| **P3 — Persuasion** | `recommend/` | `features/why-panel/` |
| **P4 — Seamless + Proof** | `session/`, `api/cart.py`, `evals/` | `features/cart/`, `oneapp/` |
| **SHARED (hour 0)** | `contracts/models.py`, `main.py`, `docker-compose.yml` | `shared/`, `api/`, `oneshop/` |

Because ownership maps to **folders**, git merge conflicts are almost impossible.

---

## 2. The Contracts (the interfaces between all 4 slices)

These are the exact shapes that flow through the pipeline. **Everyone codes against these.** Any change must be announced to the whole team.

### Pipeline data flow
```
POST /chat { session_id, message }
   → [P4] load session (history, profile, cart)
   → [P1] Intent + updated Preference Profile
   → [P2] Retrieval: candidate products (Qdrant)
   → [P2] Engine: filter to ELIGIBLE products (deterministic)
   → [P3] Rank + "why" + Next-Best-Action
   → ChatResponse (reply, recommendations, nba, cart, receipts)
```

### Core shapes (mirror these in `contracts/models.py`)

```jsonc
// PRODUCT — a catalog item (P2 owns)
{
  "id": "phone_pixel8",
  "type": "phone",                 // phone | plan | accessory | bundle
  "name": "Google Pixel 8",
  "brand": "Google",
  "description": "Flagship camera phone with AI photo tools",
  "price_monthly": 0,              // for device-on-plan
  "price_onetime": 799,
  "category": "phones",
  "features": ["camera", "5g", "eu_roaming"],
  "compatible_plans": ["plan_m", "plan_l"],
  "stock": 12,                     // LIVE fact — checked, never embedded
  "in_stock": true
}

// PREFERENCE PROFILE (P1 owns, P4 persists in session)
{
  "budget_monthly_max": 40,
  "brands_viewed": ["Samsung", "Google"],
  "features_mentioned": ["camera", "eu_roaming"],
  "categories_browsed": ["phones"],
  "rejected": ["iphone_16_pro"]
}

// INTENT (P1 output)
{
  "use_case": "photography and travel",
  "budget_monthly_max": 40,
  "priority_features": ["camera", "eu_roaming"],
  "product_types": ["phone", "plan"],
  "clarification_needed": false,
  "clarification_question": null,
  "profile": { /* PreferenceProfile */ }
}

// ELIGIBLE PRODUCT (P2 engine output)
{
  "product": { /* Product */ },
  "eligible": true,
  "reasons": ["in stock", "within budget"],
  "failed_rules": []               // e.g. ["over_budget"] when eligible = false
}

// RECOMMENDATION (P3 output)
{
  "product_id": "phone_pixel8",
  "rank": 1,
  "score": 0.92,
  "why": "Best camera in your budget; plan includes EU roaming for your travel.",
  "bundle": ["plan_m", "accessory_case"]
}

// CART (P4 owns)
{
  "session_id": "abc123",
  "items": [ { "product_id": "phone_pixel8", "qty": 1, "price": 799 } ],
  "subtotal": 799,
  "free_shipping_threshold": 50
}

// CHAT RESPONSE (the API returns this)
{
  "reply_text": "Here are two great fits...",
  "recommendations": [ /* Recommendation[] */ ],
  "nba": ["Add a €15 case?", "You're €5 from free shipping"],
  "cart": { /* Cart */ },
  "receipts": {                    // the "keep receipts" trust feature
    "retrieved_ids": ["phone_pixel8", "phone_s24"],
    "rules_fired": ["within_budget", "in_stock"],
    "shown_ids": ["phone_pixel8"]
  }
}
```

---

## 3. Detailed per-person tasks (phased)

Each person's work is broken into **Setup → Mock → Real → Polish**. The "Mock" phase is what everyone finishes by Hour 2.

### P1 — Brain (orchestration, intent, conversation, preference profile)
**Exposes:** the `/chat` endpoint that runs the whole pipeline; the `Intent` object; the updated `PreferenceProfile`.
**Consumes:** P2 retrieval + engine, P3 recommend, P4 session (all via contracts — mock them until ready).

- **Setup:** Set up LangGraph; wire `ChatXAI` (Grok) with an API key; a graph with nodes: `intent → retrieve → filter → recommend → respond`.
- **Mock:** Each node calls a stub that returns contract-shaped mock data. `/chat` returns a full `ChatResponse` from mocks. **This is the integration backbone — get it working first, it unblocks everyone.**
- **Real:** Implement the intent node (Grok extracts budget/features/use-case from the message + history). Implement the preference profile update logic. Handle `clarification_needed`.
- **Polish:** Multi-turn memory, "listens and adapts" behavior, prompt tuning.
- **Frontend:** `features/chat/` — message list + input box + streaming display.
- **Senior story:** "Why multi-agent/graph over one prompt — auditable, testable per node, resumable."

### P2 — Truth (RAG retrieval + deterministic eligibility engine + catalog)
**Exposes:** `retrieve(intent) -> Product[]` (candidates) and `filter_eligible(products, intent) -> EligibleProduct[]`.
**Consumes:** nothing (you're the foundation — build first, everyone depends on your data).

- **Setup:** Generate `catalog.json` (~100–150 items: phones, MagentaMobil plans, accessories, bundles) — **do this in Hour 0, everyone needs it.** Stand up Qdrant via Docker.
- **Mock:** `retrieve()` returns a fixed slice of the catalog; `filter_eligible()` returns everything marked eligible. Publish these so P1/P3 can build.
- **Real:** Embed catalog with sentence-transformers → upsert to Qdrant. Implement semantic `retrieve()` (top-k). Implement the **deterministic eligibility engine**: pure functions for `in_stock`, `within_budget`, `plan_compatible`, etc. — same input → same output, always.
- **Polish:** Metadata filtering, the "flip a product to out-of-stock" demo hook, tidy `reasons`/`failed_rules`.
- **Frontend:** `features/product-card/` — card showing price, an **in-stock badge**, eligibility.
- **Senior story:** "The LLM can't hallucinate a product — the engine is the source of truth, and it's deterministic and reproducible."

### P3 — Persuasion (ranking, "why this", Next-Best-Action, Smart Cart nudges, guardrails)
**Exposes:** `recommend(eligible_products, profile) -> {recommendations[], nba[]}`.
**Consumes:** P2's `EligibleProduct[]` and P1's `PreferenceProfile` (mock both until ready).

- **Setup:** A `recommend/` module skeleton returning contract-shaped data.
- **Mock:** Return a hardcoded ranked list + fake "why" + fake nudges. Unblocks P1's pipeline wiring.
- **Real:** Rank eligible products using the preference profile (simple scoring — feature match, brand affinity, budget fit). Use Grok to generate the personalized **"why this?"** text from the product + profile. Implement **NBA / smart-cart nudges** (bundle suggestion, "€X from free shipping"). Add the **guardrail**: never output a product not in the eligible list (anti-hallucination check).
- **Polish:** Tune explanations to be short and personal; add compare ("A vs B").
- **Frontend:** `features/why-panel/` — the "Why this?" panel + nudge banners.
- **Senior story:** "How I make AI legible to the customer and stop it from ever recommending junk."

### P4 — Seamless + Proof (session, cart, checkout, omnichannel, eval harness, demo)
**Exposes:** session load/save; `Cart`; cart & checkout endpoints; the eval harness.
**Consumes:** the `/chat` response (to persist history/profile/cart).

- **Setup:** `session/` module — in-memory session store keyed by `session_id` (history + profile + cart). `api/cart.py` with `/cart/add`, `/cart/remove`, `/checkout`.
- **Mock:** Session returns an empty session; cart returns a fixed cart. Unblocks P1.
- **Real:** Persist conversation history, preference profile, and cart per session. Implement cart math (subtotal, free-shipping threshold). Implement mock checkout (summary → confirm). Build the **mobile view** (`oneapp/`) that reuses components but reads the **same `session_id`** → proves omnichannel.
- **Proof:** Build the **eval harness** in `evals/` — a set of test queries with expected grounded behavior (e.g., "must refuse out-of-catalog", "must stay in budget"), run as a script that prints pass/fail.
- **Polish:** Demo orchestration, seed data for the demo, rehearsal support.
- **Senior story:** "State continuity across channels is a distributed-systems problem — and here's how I *prove* the whole thing works (evals)."

---

## 4. How to use YOUR OWN AI tool effectively (Cursor / Claude Code / Copilot / etc.)

Everyone can use a different AI assistant — that's fine. To keep 4 AIs from producing 4 incompatible styles:

1. **Feed your AI the context every session:** paste (a) your task section from this file, and (b) `contracts/models.py`. Tell it: *"All data must conform to these contracts. Do not invent new shapes."*
2. **Never let the AI change a contract silently.** If your AI wants a new field, that's a team decision — announce it.
3. **Verify, don't paste blindly.** This is literally scored in the individual round ("do they verify AI output or paste"). After AI writes code: read it, run it, check it against the contract. Be ready to explain *why* it works.
4. **Commit your own work under your own name.** Judges cross-check commits and will ask you about your code — and about a teammate's. No single person merges everything.
5. **Keep prompts + decisions noted** — a few lines per feature ("asked AI for X, rejected Y because Z"). Great material for the individual round and shows engineering judgement.

---

## 5. Git workflow (fast, low-conflict)

- **Branches:** one per person — `feat/p1-agents`, `feat/p2-truth`, `feat/p3-recommend`, `feat/p4-session`. `main` stays runnable.
- **Commits:** small, frequent, **under your own name**. Meaningful messages.
- **Merging:** because folder ownership is separated, conflicts are rare. Merge to `main` at each **integration checkpoint** (below). A rotating "integration lead" (start with P4) does a 5-min sanity check before merging.
- **The one shared file to be careful with:** `contracts/models.py`. Change it only by team agreement; announce it; everyone pulls immediately after.
- **`main` must always run.** If your merge breaks `main`, you fix it or revert — don't leave it red (this is exactly the "leave the workspace green" discipline DTDL praises).

---

## 6. Integration cadence (when everyone syncs)

| Checkpoint | Time | Goal |
|---|---|---|
| **C0 — Kickoff** | Hour 0–1 | Together: repo, `docker-compose` (Qdrant), `contracts/models.py`, `catalog.json`, shared React shell. Agree contracts out loud. |
| **C1 — Mock end-to-end** | Hour 2 | The whole app runs on mock data: type a message → get a full `ChatResponse` in the UI. **Everyone unblocked from here.** |
| **C2 — Real cores** | Hour 6 | Each person's real implementation replaces their mock; integrate to `main`. |
| **C3 — Full flow** | Hour 10–12 | Real end-to-end: ask → grounded recs → why → cart. |
| **C4 — Depth** | Hour 16–18 | Personalization, NBA, omnichannel, guardrails, receipts working. |
| **C5 — Proof + freeze** | Hour 20–21 | Eval harness green; feature freeze. |
| **C6 — Rehearse** | Hour 21–23 | Demo run-through ×3; each person rehearses their "senior story". |

> The magic checkpoint is **C1**. Once the app runs on mocks, integration risk is basically gone — everyone just swaps their own mock for real code.

---

## 7. Communication plan

- **Standups every ~3–4 hours (15 min max):** what I finished, what I'm blocked on, any contract change.
- **One shared chat channel.** Any change to `contracts/models.py` gets posted there immediately: *"Contract change: added `X` to Recommendation — pull now."*
- **This doc is the source of truth.** If a decision changes, update the doc so nobody works off stale assumptions.
- **Blocked? Mock it and move on.** Never sit idle waiting for someone — the whole point of mock-first is you can always keep building against the contract.

---

## 8. Quick summary

- **Contracts first, mocks by Hour 2, then everyone works alone against the contract.**
- **Folder ownership** = no merge conflicts.
- **Each person owns one vertical slice** (AI + backend + their UI) — everyone touches AI, nobody is "just frontend."
- **P1 makes it smart · P2 makes it honest · P3 makes it persuasive · P4 makes it seamless.**
- Use your own AI tool, but **always conform to the contracts and verify the output.**
