# AI Brief — P3: Persuasion (ranking · "why this" · Next-Best-Action · guardrails)

> **How to use this file:** paste it into your AI together with
> `backend/app/contracts/models.py`. Tell the AI: *"Conform to these contracts, extend the
> existing stubs, keep their signatures, put heavy imports inside functions."*

## Project context
Trustworthy Telekom shopping assistant. Core principle: **AI generates, deterministic rules
decide.** You make recommendations *persuasive and legible* — and you enforce the
anti-hallucination guardrail. Your work directly moves the business metric (conversion /
cart abandonment).
Pipeline: intent (P1) → retrieve (P2) → eligibility (P2) → **recommend (you)** → response.

## Your job
Rank the eligible products for THIS user, explain **why** each fits them personally, and nudge
them through the funnel (bundles, add-ons, checkout) — without ever recommending junk.

## Files you own
- `backend/app/recommend/recommender.py` — `recommend(eligible, profile, cart) -> (recs, nba)`.
- `frontend/src/features/why-panel/WhyPanel.jsx` — nudges + trust receipts panel.
  (The per-recommendation "why" text renders on P2's ProductCard — you supply the text.)

## Contracts you produce / consume
- **Produce:** `Recommendation[]` (`product_id`, `rank`, `score`, `why`, `bundle`) and `nba: string[]`.
- **Consume:** `EligibleProduct[]` (P2), `PreferenceProfile` (P1), `Cart` (P4).

## Current state (already working in mock mode)
- `recommender.py` scores by feature/brand match + budget fit, writes a template `why`, and
  generates simple nudges. The guardrail (recs ⊆ eligible) is enforced upstream in `graph.py`.

## Your tasks
**REAL — explanations via Grok** (`recommend/recommender.py::_why_grok`)
- Generate a short, personal "why this fits you" from the product's REAL fields + the profile.
- Import `langchain_xai.ChatXAI` inside the function.
- **Grounding rule:** the prompt must forbid mentioning features the product doesn't have.
  On any error, fall back to `_why_template`.

**REAL/EXTEND — ranking & personalization**
- Improve `_score` using the `PreferenceProfile` (feature match, brand affinity, rejected
  brands penalty, budget headroom). Keep it deterministic and explainable.

**REAL/EXTEND — Next-Best-Action / Smart Cart**
- Smarter nudges: complementary accessories for the chosen phone, plan upsell, bundle deals,
  "€X from free shipping" (use the `Cart`), "customers also added…".

**POLISH**
- "Compare A vs B" explanations.
- Tune tone to be short, warm, specific.
- Frontend: make the nudges and the trust "receipts" panel look great (this is very
  demo-visible).

## How to mock what you don't have
`EligibleProduct[]` and `PreferenceProfile` are already real. If you want richer test data,
hardcode a small `eligible` list and call `recommend()` directly.

## Rules for your AI
- **Never output a `product_id` that isn't in the `eligible` input.** (Also enforced in `graph.py`.)
- The `why` must be grounded only in the product's real fields — no invented specs.
- Keep `MOCK_MODE` working: real Grok behind `_why_grok`; import langchain inside the function.

## Your "senior story" (rehearse for the individual round)
*"My job is to make AI recommendations both persuasive and trustworthy. Ranking is
deterministic and explainable from the preference profile; the LLM only phrases the 'why',
grounded strictly in real product fields, and can never introduce a product the engine
rejected. The nudges are where we move cart abandonment."*
Be ready for: *"how do you stop it recommending junk / hallucinating?"* → the guardrail
(recs must be a subset of eligible ids) + grounded prompts + a template fallback.
