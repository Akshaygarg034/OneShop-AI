# AI Brief — P1: The Brain (orchestration · intent · conversation · preference profile)

> **How to use this file:** paste it into your AI assistant together with
> `backend/app/contracts/models.py`. Tell the AI: *"Conform to these contracts, extend the
> existing stubs, keep their signatures, put heavy imports inside functions."*

## Project context
We're building a trustworthy Telekom shopping assistant. Core principle:
**AI generates, deterministic rules decide** — the LLM converses/ranks/explains, but a
deterministic engine (P2) decides what's actually offerable, so it never hallucinates.
Pipeline: **intent (you) → retrieve (P2) → eligibility (P2) → recommend (P3) → response**.

## Your job
Make the assistant *understand* the user and run the whole loop. You own the conversation
brain and the pipeline backbone.

## Files you own
- `backend/app/agents/intent.py` — extract structured `Intent` from a message.
- `backend/app/agents/profile.py` — update the `PreferenceProfile` (learning).
- `backend/app/agents/graph.py` — the orchestrator (turn this into a LangGraph graph).
- `backend/app/api/chat.py` — the `/chat` endpoint (already wired).
- `frontend/src/features/chat/Chat.jsx` — the chat UI.

## Contracts you produce / consume
- **Produce:** `Intent` (with nested `PreferenceProfile`), and the final `ChatResponse`.
- **Consume:** `retrieve()` (P2), `filter_eligible()` (P2), `recommend()` (P3), the `Session` (P4).
  All already exist as working mocks — you're never blocked.

## Current state (already working in mock mode)
- `intent.py` has a regex/keyword mock that fills `Intent`.
- `graph.py` runs the full pipeline as plain function calls and enforces the guardrail.
- `/chat` loads the session, runs the pipeline, returns `ChatResponse`.

## Your tasks
**REAL — intent via Grok** (`agents/intent.py::_extract_real`)
- Call Grok with `langchain_xai.ChatXAI` (import inside the function).
- Prompt it to return JSON matching the `Intent` contract: `use_case`, `budget_monthly_max`,
  `priority_features`, `product_types`, `clarification_needed`, `clarification_question`.
- Parse + validate into `Intent`. Keep the SAME signature as `_extract_mock`.
- Feed in `history` for multi-turn understanding.

**REAL — orchestration via LangGraph** (`agents/graph.py`)
- Convert `run_pipeline` into a LangGraph `StateGraph`: nodes = intent, retrieve, filter,
  recommend, respond; a conditional edge for `clarification_needed`; (optional) a retry edge.
- Keep calling the same node functions — only the wiring changes. The guardrail
  (recs ⊆ eligible ids) must stay.

**POLISH**
- Multi-turn memory; "listens and adapts" (if the user changes their mind, intent reflects it).
- Tune prompts so clarification triggers only when genuinely vague.
- Frontend: streaming display, nicer message rendering.

## How to mock what you don't have
Everything you depend on already returns real contract-shaped data. If P2/P3 change, you're
unaffected as long as the contract holds.

## Rules for your AI
- Never introduce a product in the reply that isn't in the eligible set (guardrail lives in `graph.py`).
- Keep `MOCK_MODE` working: real Grok code goes behind the `if MOCK_MODE` branch / `_real` funcs.
- Import `langchain_xai` inside functions, not at module top.

## Your "senior story" (rehearse for the individual round)
*"Why a LangGraph graph instead of one big prompt? Because each role is independently testable,
the flow is auditable, it supports retries and a human/clarification branch, and it's resumable.
The model proposes; the graph enforces the guardrail that only eligible products reach the user."*
Be ready for: *"what breaks at DT scale?"* → LLM latency per turn; cache common intents, run
independent nodes in parallel, keep the graph stateless behind a shared session store.
