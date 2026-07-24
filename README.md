# Telekom Smart Shopping Assistant

An AI shopping assistant for Deutsche Telekom (DTDL Talent Hack, Problem Statement 5).
Grounded, trustworthy product recommendations across web (OneShop) and mobile (OneApp).

> **New here? Read [`START_HERE.md`](START_HERE.md) first.**
> Full plan: [`PROJECT_OVERVIEW.md`](PROJECT_OVERVIEW.md) · Who-does-what: [`TEAM_TASKS_AND_WORKFLOW.md`](TEAM_TASKS_AND_WORKFLOW.md)

## Quick start (mock mode — no API keys needed)

**Backend**
```bash
cd backend
python -m venv .venv && source .venv/Scripts/activate   # Windows Git Bash
pip install fastapi "uvicorn[standard]" pydantic python-dotenv
cp .env.example .env          # MOCK_MODE=true by default
uvicorn app.main:app --reload
# -> http://localhost:8000/docs
```

**Frontend**
```bash
cd frontend
npm install
npm run dev
# -> http://localhost:5173
```

**Run the eval harness (proof it works)**
```bash
cd backend && python -m evals.run_evals
```

## How it works (the core idea)

> **AI generates. Deterministic rules decide.**
> The LLM (OpenAI) converses, ranks, and explains. A deterministic engine decides what's
> actually offerable (stock / budget / eligibility). The AI can never recommend a product
> the rules reject — so it never hallucinates.

Pipeline: `intent (P1) → retrieve (P2) → eligibility (P2) → recommend (P3) → response`,
with session/cart/omnichannel by P4.

## Mock-first workflow

The whole app runs on **mock data** today (`MOCK_MODE=true`). Each person replaces their own
mock with real code, then flips their part to real — nobody is blocked. See
[`TEAM_TASKS_AND_WORKFLOW.md`](TEAM_TASKS_AND_WORKFLOW.md).

## Stack

OpenAI · LangGraph · FastAPI · Qdrant + sentence-transformers · React (Vite)
