# Telekom Smart Shopping Assistant — Project Overview

> **DTDL "The Talent Hack" — Build Sprint**
> **Problem Statement 5:** Build an Omnichannel Consumer AI Engine for Digital Commerce
> A shareable overview for the whole team. Read this first.

---

## 1. The one-line pitch

> **A trustworthy AI shopping assistant for Deutsche Telekom that helps a customer find the right phone + plan + accessories through natural conversation, explains *why* each choice fits *them*, learns their preferences as they browse, and guides them all the way to checkout — consistently across web (OneShop) and mobile (OneApp).**

The differentiator in one sentence:

> **Most shopping bots just chat. Ours recommends only *real, in-stock, eligible* products, *explains why*, *learns preferences*, *nudges toward checkout*, and *carries the session across devices* — the AI recommends and explains, but deterministic rules decide what's actually offerable, so it never hallucinates a product.**

---

## 2. The problem we're solving (why this matters)

- **User:** a Telekom customer who wants a new phone/plan but is overwhelmed by thousands of devices, plans, and accessories.
- **Pain:** too much choice → confusion → they leave without buying, or abandon a half-full cart.
- **Business metric we move:** **conversion rate** and **cart abandonment %** (started carts that never complete — typically ~70% in e-commerce).

We are not "building a chatbot." We are attacking **cart abandonment and poor product discovery**, which is direct revenue for a commerce business like Telekom's OneShop.

---

## 3. What we're building (in plain words)

An assistant that behaves like a **knowledgeable, honest salesperson** who never forgets what you said. The customer types (or speaks) what they want in natural language, and the system:

1. **Understands** what they really need (budget, use-case, preferences).
2. **Finds** matching products from the real Telekom catalog (not made-up ones).
3. **Filters** to what's actually offerable (in stock, in budget, plan-compatible).
4. **Recommends & ranks** the best 2–3 options — personalized to what they've shown interest in.
5. **Explains why** each option fits *them*, in plain language.
6. **Nudges them forward** (bundles, accessories, "almost at free shipping," checkout help).
7. **Follows them** from web to mobile without losing the conversation or cart.

### The whole funnel — on a trust layer

```
DISCOVER  →  DECIDE  →  CART  →  CHECKOUT  →  CROSS-CHANNEL
(chat +      (compare,   (bundle    (checkout    (web → mobile,
 personalized "why this")  nudges)    assist)      context persists)
 grounded recs)
        └──────────────── TRUST LAYER underneath ────────────────┘
     grounded in real catalog · never hallucinates a product ·
     explains itself · learns preferences · refuses gracefully ·
     logs every decision (receipts)
```

**Most teams will demo only the first box (chat). We demo the whole line + the trust layer.** That is our edge.

---

## 4. The core principle (the DTDL theme)

> **AI generates. Deterministic rules decide.**

- The **AI (Grok)** converses, understands intent, ranks candidates, and explains recommendations.
- A **deterministic engine** (plain code) is the source of truth for what is *actually offerable* — stock, price/budget, plan compatibility, eligibility.
- The AI can **propose**, but it can **never** put a product in front of the customer that the rules reject.

This is why the assistant is **trustworthy**: it physically cannot recommend a phone that doesn't exist, is out of stock, or breaks the budget. Every problem statement in this hackathon repeats this theme ("AI generates, checks accept") — we bring it to a consumer product.

---

## 5. Key features (what makes it deep, not a toy)

| # | Feature | Why it matters |
|---|---------|----------------|
| 1 | **Grounded recommendations** | AI recommends only from real retrieved catalog items; never hallucinates. (Trust) |
| 2 | **"Why this for you?"** | Every recommendation carries a plain-English, personalized justification. (Trust + conversion) |
| 3 | **Live preference learning** | A session profile updates as the user searches/clicks and biases ranking. (Personalization) |
| 4 | **Next-Best-Action nudges** | Bundle suggestions, accessory add-ons. (Moves the business metric) |
| 5 | **Smart Cart & Checkout** | Cart with intelligent nudges ("€5 from free shipping"), bundle suggestions, and a guided (mock) checkout assist. (Directly reduces cart abandonment) |
| 6 | **Graceful clarification & refusal** | Asks one smart question when unsure; refuses/redirects when it can't help safely. (Knows when to ask) |
| 7 | **Omnichannel continuity** | Same session + cart from web (OneShop) to mobile view (OneApp). (The literal ask) |
| 8 | **Decision receipts** | Every recommendation logs what was retrieved, which rules fired, what was shown. (Auditable) |

> **Build the core fully; mention any extras as "how we'd extend it" to show breadth without over-scoping.**

### Coverage of the 5 expected capabilities (from the problem statement)

The statement says "implement **one or more**" — we cover all five, at a demonstrable level:

| Expected capability | Covered? | Where in our build |
|---|---|---|
| Personalized Discovery | ✅ | Preference profile → biased, grounded recommendations |
| Conversational Shopping Assistant | ✅ | The chat itself — discover, compare, select in natural language |
| Next Best Action | ✅ | Contextual nudges that guide through the funnel |
| **Smart Cart & Checkout** | ✅ | Cart + bundle/upsell nudges + guided (mock) checkout assist |
| Omnichannel Experience | ✅ | Shared session + cart across web (OneShop) and mobile view (OneApp) |

> **Note on checkout:** we build a **mock checkout flow** (cart → summary → "place order" confirmation) with the assistant helping. We do **not** integrate real payments — that's out of scope for a 24h POC, and saying so is a good "deliberate trade-off" answer.

---

## 6. The live preference profile (our personalization approach)

We do **not** build a machine-learning recommender or a real-time training pipeline (too big, needs real data, un-demoable in 24h).

Instead, we keep a **lightweight preference profile** that updates as the user interacts and feeds it to the recommendation step as context:

```json
{
  "budget_range": "<= 40 EUR/mo",
  "brands_viewed": ["Samsung", "Google"],
  "features_mentioned": ["camera", "EU roaming"],
  "categories_browsed": ["phones", "cases"],
  "rejected": ["iPhone (too expensive)"]
}
```

- The recommendation step reads this profile and **biases the ranking** (matching products rank higher).
- The deterministic engine **still filters** — personalization changes *ordering*, never lets junk through.
- **Explainability upgrade:** "why this?" becomes *"because you looked at cameras and set a 40 EUR budget, and skipped the iPhone."*
- **Cold start handled:** first-time user with no history → fall back to the current query's intent.
- **Correctable:** if the user says "actually show me iPhones," the profile updates — it listens, it doesn't stubbornly cling.

---

## 7. How it works (architecture)

```
┌──────────── OneShop (Web, React) ────────────┐   ┌── OneApp (phone-shaped web view) ──┐
│  Chat + product cards + "Why this?" panel      │   │  Same session → cart continues     │
└──────────────────────┬──────────────────────────┘   └───────────────┬────────────────────┘
                       │        (shared session_id / preference profile)  │
                       └──────────────────────┬───────────────────────────┘
                                              ▼
                                 FastAPI backend (Python)
                                              │
                 ┌──────────── LangGraph multi-agent orchestrator ───────────┐
                 │  • Intent/Profile agent → understands need + updates profile│
                 │  • Retrieval agent      → RAG over product catalog          │
                 │  • Recommendation agent → ranks grounded candidates         │
                 │  • Explanation agent    → "why this fits you"               │
                 │  • Next-Best-Action     → nudge / bundle / checkout         │
                 └───────────────┬───────────────────────┬───────────────────┘
                                 ▼                       ▼
                Deterministic Eligibility Engine     Vector DB (Chroma) + Catalog
                (source of truth: stock, budget,     (semantic search over real
                 plan compatibility, price)           Telekom products) + session store
```

**Key idea:** RAG finds *relevant* products by meaning; the deterministic engine checks *live truth* (stock/price/eligibility). Volatile facts (stock) are NOT stored in the vector DB — they're checked live at query time.

---

## 8. Tech stack

| Layer | Choice |
|-------|--------|
| LLM (generation) | **Grok (xAI API)** — via `langchain-xai` (`ChatXAI`) so LangGraph can drive it |
| Embeddings (for RAG) | **Open-source embedding model** (e.g., `sentence-transformers/all-MiniLM-L6-v2`) — runs locally, free. *(xAI/Grok has no embeddings API, so generation and embeddings use different models — this is normal.)* |
| Orchestration | LangGraph (multi-agent, stateful) |
| Backend | Python + FastAPI |
| Vector DB / RAG | **Qdrant** (run locally via Docker) + the embedding model above |
| Source of truth | Deterministic Python eligibility engine |
| Catalog data | Mock Telekom catalog (~100–150 items: phones, MagentaMobil plans, accessories, bundles) — we generate it |
| Frontend | React — OneShop web + phone-shaped OneApp web view (no native app needed) |
| Proof | Small eval harness (test queries → expected grounded behavior) |

> **Important embeddings note:** Grok is used for *conversation and reasoning*. For *RAG search* you need an **embedding model**, and xAI doesn't provide one — so we use a free local model (sentence-transformers) to turn catalog text into vectors for Qdrant. Two models, two jobs: Grok reasons, MiniLM embeds.

> **Note on "mobile":** OneApp is represented as a **mobile-shaped web view**, not a native app. In production it would be the native app hitting the same backend API. This is an honest, legitimate way to demo omnichannel with an all-web team.

---

## 9. Example scenarios (what it actually does)

### Scenario A — Guided discovery (the happy path)
**Customer:** "I need a new phone under 40 euros a month, I take a lot of photos and I travel around Europe."
1. Intent agent extracts: budget ≤ €40/mo, priority = camera, needs EU roaming. Profile updated.
2. Retrieval finds candidate phones + plans matching "good camera."
3. Eligibility engine drops anything out of stock or over budget.
4. Recommendation agent returns 2–3 phone + plan bundles.
5. **Assistant:** "Here are two great fits. The **Pixel 8 + MagentaMobil M** is my top pick — best camera in your budget, and the plan includes EU roaming for your travel."
6. Each card shows a **"Why this?"** panel.

### Scenario B — Trust / anti-hallucination (the moment that wins the room)
**Customer:** "Actually, can you get me an iPhone 16 Pro for 20 euros a month?"
- The engine finds no eligible option in that budget.
- **Assistant:** "I can't offer the iPhone 16 Pro at €20/mo — it starts at €55/mo on our plans. Want me to show the closest iPhone in your budget, or a similar camera phone under €40?"
- **It refuses to invent a product or a fake price.** (Deterministic rules winning over the LLM.)

### Scenario C — Personalization / learning
- After the customer views two Samsung phones and skips an iPhone, the profile learns: brand affinity = Samsung/Android, rejected iPhone.
- Next recommendation ranks Android phones higher.
- **Assistant:** "Since you've been looking at Samsung and Google phones, here's the best Android camera phone in your budget."

### Scenario D — Next-Best-Action / reduce abandonment
- Customer adds a phone to cart.
- **Assistant:** "Good choice. This phone pairs well with a €15 case — add it? Also, you're €5 away from free shipping."
- Gentle nudge → higher cart value + lower abandonment.

### Scenario E — Clarification over guessing
**Customer:** "I want something good and cheap."
- Ambiguous. Instead of dumping 50 products:
- **Assistant:** "Happy to help! Quick question — is this mainly for calls and messaging, or do you want a strong camera and gaming too? And what monthly budget works for you?"

### Scenario F — Omnichannel continuity
- Customer starts on **web** at their desk, gets recommendations, adds a phone to cart.
- Opens the **mobile view** later → same conversation history, same cart, same learned preferences.
- Completes checkout on mobile.

### Scenario G — Graceful refusal (safety)
**Customer:** "Cancel my existing contract and delete my account."
- Out of scope / consequential.
- **Assistant:** "I can help you shop for devices and plans, but account changes like cancellations need to go through Telekom support — here's how to reach them." (Knows its limits.)

---

## 10. Individual contributions (4 people, vertical slices)

**Principle:** each person owns one feature **end-to-end** — its AI logic + API + its slice of UI. **Nobody is "just frontend"; everybody owns AI.** This also makes ownership provable in commits (judges cross-check this).

| Person | Owns end-to-end | Customer value | Their "senior story" (individual round) |
|--------|-----------------|----------------|------------------------------------------|
| **P1 — Brain** | LangGraph orchestration, intent understanding, conversation flow, **live preference profile** | Feels like talking to a smart human who *gets* you | "Why multi-agent over one prompt — auditable, testable, resumable" |
| **P2 — Truth** | RAG retrieval + **deterministic eligibility engine** (stock / budget / compatibility) + catalog data | Every recommendation is a real, buyable, in-stock product | "The LLM can't hallucinate a product — rules are the source of truth" |
| **P3 — Persuasion** | **"Why this for you?"** explainer + Next-Best-Action nudges + preference-based ranking + guardrails | Customer understands & trusts the rec, and finishes the purchase | "How I make AI legible and stop it recommending junk" |
| **P4 — Seamless + Proof** | Shared session (web ↔ mobile view) + cart continuity + **eval harness** + demo orchestration | Same conversation & cart across devices; proof it works | "State continuity is a distributed problem — and here's how I *prove* it works" |

**Simple summary:**
> **P1 makes it smart · P2 makes it honest · P3 makes it persuasive · P4 makes it seamless.**

### Shared work — done together in Hour 0 (~1–2 hrs)
- **30-min whiteboard:** agree the **JSON contracts** between agents/APIs, so 4 people build in parallel without colliding.
- **Shared React shell:** one person scaffolds the chat window, product card, and layout that everyone drops their feature UI into.
- **Catalog data:** generate the mock Telekom catalog together, so everyone builds against the same products.

---

## 11. 24-hour timeline

| Hours | Focus |
|-------|-------|
| 0–2 | Lock the slice + data schema. Generate catalog. Skeleton: one message round-tripping through the whole stack (React → FastAPI → LangGraph → Grok → back). |
| 2–8 | Parallel build — P1: agents; P2: RAG + eligibility; P3: explainer UI; P4: session sharing. |
| 8–12 | Integrate → first full flow working (ask → grounded recs → explanation). Sleep in shifts. |
| 12–18 | Explainability polish, next-best-action, preference learning, omnichannel continuity, guardrails. |
| 18–21 | Eval harness + failure hardening. |
| 21–23 | Freeze features. Rehearse the 5–7 min demo end-to-end 3×. |
| 23–24 | Buffer for breakage. |

---

## 12. Demo script (5–7 min, rehearse 3×)

1. **Web:** "I need a phone under €40/mo, I stream a lot and travel in Europe." → assistant asks one smart question → returns 2–3 grounded bundles with a **"Why this?"** panel.
2. **Trust moment:** ask for something out-of-budget / out-of-stock → it **refuses / stays grounded** (deterministic engine wins).
3. **Personalization:** show it adapting as preferences emerge.
4. **NBA:** add an accessory → smart-cart nudge.
5. **Omnichannel:** switch to phone view → same session + cart → checkout.
6. **Close (30s):** architecture diagram + the line: *"AI generates, deterministic rules decide — that's why it's trustworthy."*

> Note: swap "Claude" for "Grok" and "Chroma" for "Qdrant" anywhere older notes mention them — the stack is **Grok + Qdrant**.

---

## 13. Failure & scale talking points (rehearse — this wins the individual round)

- **What breaks at DT scale (18M users)?** → LLM latency + DB queries; fix with caching (embeddings + common intents), parallel agent calls, stateless services + Redis session store.
- **How do you know it works?** → the eval harness + the guardrail that provably blocks out-of-catalog recommendations.
- **What did you deliberately cut (debt)?** → mock catalog (vs real OneShop API), in-memory session (vs Redis), single model everywhere.
- **What's next with a week?** → real catalog API, re-ranking, persistent per-customer profiles, A/B testing the recommendations.

---

*This document is the shared source of truth for the team. Keep it updated as decisions change.*