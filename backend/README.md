# Backend — Telekom Smart Shopping Assistant

FastAPI + LangGraph + Grok + Qdrant. Runs on **mock data** out of the box (no keys).

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
```bash
pip install -r requirements.txt          # adds langgraph, langchain-xai, qdrant, embeddings
docker compose up -d qdrant              # from repo root, for P2
# set XAI_API_KEY in .env, and flip MOCK_MODE=false when your slice is ready
```

## Layout (folder = owner)
```
app/
  contracts/models.py   SHARED  - data shapes (single source of truth)
  agents/               P1      - intent, profile, graph orchestrator
  retrieval/            P2      - Qdrant RAG + catalog loader
  engine/               P2      - deterministic eligibility engine
  recommend/            P3      - ranking, "why", next-best-action
  session/              P4      - session store, cart, checkout
  api/                  chat.py(P1) cart.py(P4) catalog.py(P2)
data/catalog.json       P2      - product data
evals/run_evals.py      P4      - proof harness
```

Key switch: `MOCK_MODE` in `.env` / `app/config.py`. See [`../START_HERE.md`](../START_HERE.md).
