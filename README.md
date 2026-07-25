# Telekom Smart Shopping Assistant

An AI shopping assistant for Deutsche Telekom (DTDL Talent Hack, Problem Statement 5). Grounded, trustworthy product recommendations across web (OneShop) and mobile (OneApp).

> **New here? Read** `START_HERE.md` **first**.Full plan: `PROJECT_OVERVIEW.md` · Who-does-what: `TEAM_TASKS_AND_WORKFLOW.md`

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

> **AI generates. Deterministic rules decide**.The LLM (OpenAI) converses, ranks, and explains. A deterministic engine decides what's actually offerable (stock / budget / eligibility). The AI can never recommend a product the rules reject — so it never hallucinates.

Pipeline: `intent (P1) → retrieve (P2) → eligibility (P2) → recommend (P3) → response`, with session/cart/omnichannel by P4.

## Mock-first workflow

The whole app runs on **mock data** today (`MOCK_MODE=true`). Each person replaces their own mock with real code, then flips their part to real — nobody is blocked. See `TEAM_TASKS_AND_WORKFLOW.md`.

## Stack

OpenAI · LangGraph · FastAPI · Qdrant + sentence-transformers · React (Vite)# 🛍️ Telekom Smart Shopping Assistant

AI-powered omnichannel shopping assistant built for the **Deutsche Telekom Talent Hack (Problem Statement 5)**.

This repository contains both the **Frontend** and **Backend** applications.

```
Smart-Shopping-Assistant/
├── backend/        # FastAPI Backend
├── frontend/       # React Frontend
├── deliverables/   # Presentation & architecture diagrams
└── docs/
```

---

# 📋 Prerequisites

Before getting started, ensure the following are installed:

- Python 3.11+
- Node.js 20+
- npm
- Git

---

# ⚙️ Backend Setup

## 1. Clone the Repository

```bash
git clone https://github.com/OmJangid206/Smart-Shopping-Assistant.git
cd Smart-Shopping-Assistant/backend
```

## 2. Create a Virtual Environment

### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
```

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 3. Install Dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 4. Configure Environment

```bash
cp .env.example .env
```

Windows

```bash
copy .env.example .env
```

Update the required values in `.env`.

## 5. Run the Backend

```bash
uvicorn app.main:app --reload
```

Backend API

```
http://127.0.0.1:8000/health
```

Swagger Documentation

```
http://127.0.0.1:8000/docs
```

---

# 💻 Frontend Setup

Open a new terminal.

```bash
cd frontend
```

Install dependencies.

```bash
npm install
```

Start the development server.

```bash
npm run dev
```

Frontend

```
http://localhost:5173
```

---


# 📚 Documentation

| Document | Description |
|----------|-------------|
| `backend/README.md` | Backend installation and configuration |
| `PROJECT_OVERVIEW.md` | Project overview |

---

# 📦 Deliverables

Presentation and high-level design (HLD) assets are in the `deliverables/` folder:

| File | Description |
|------|-------------|
| `deliverables/Smart_Shopping_Assistant.pptx` | Project presentation (PowerPoint) |
| `deliverables/high_level_diagram.svg` | High-level architecture diagram (SVG) |
| `deliverables/Smart_Shopping_Assistant_Architecture.drawio` | Editable architecture diagram (draw.io) |