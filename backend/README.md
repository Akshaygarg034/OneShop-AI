# 🛍️ Telekom Smart Shopping Assistant – Backend

> AI-powered conversational commerce backend built with **FastAPI, LangGraph, OpenAI, Qdrant, and Supabase**.

This backend powers the Telekom Smart Shopping Assistant by understanding customer intent, retrieving relevant products, applying business rules, and generating personalized recommendations.

---

# 📋 Table of Contents

- Overview
- Project Structure
- Installation
- Running the Application
- Production Setup
- Environment Variables

---

# 🚀 Overview

Key capabilities include:

- 🤖 Conversational AI shopping assistant
- 🔍 Intelligent product search
- 🎯 Personalized recommendations
- 🛒 Shopping cart management
- 👤 User authentication
- 🧠 Session management
- ⚡ Deterministic recommendation engine
- 📦 Product catalog

---

# 📁 Project Structure

```text
backend/
├── app/
├── data/
├── evals/
├── requirements.txt
├── update_catalog.py
├── .env.example
├── README.md
└── ARCHITECTURE.md
```

---

# ⚙️ Installation

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

Create a local environment file.

### Linux / macOS

```bash
cp .env.example .env
```

### Windows

```bash
copy .env.example .env
```

Update the required values in `.env`.

---

# Run the Application

Start the FastAPI development server.

```bash
uvicorn app.main:app --reload
```

The application will be available at:

- **API:** http://127.0.0.1:8000
- **Swagger UI:** http://127.0.0.1:8000/docs

Verify the installation:

```text
GET http://127.0.0.1:8000/health
```

Expected response:

```json
{
  "status": "ok"
}
```

---

# ☁️ Production Setup

## OpenAI

```text
OPENAI_API_KEY=your-api-key
MOCK_MODE=false
```

## Supabase

```text
SUPABASE_URL=your-supabase-url
SUPABASE_KEY=your-supabase-key
```

## Qdrant

Start Qdrant:

```bash
docker compose up -d qdrant
```

Generate embeddings:

```bash
python -m app.rag.ingestion
```

Enable semantic retrieval:

```text
RAG_ENABLED=true
```

---

# ⚙️ Environment Variables

| Variable | Description |
|----------|-------------|
| `MOCK_MODE` | Enable or disable OpenAI integration |
| `RAG_ENABLED` | Enable semantic retrieval |
| `CATALOG_BACKEND` | Catalog backend (`auto` or `json`) |
| `SESSION_BACKEND` | Session backend (`memory`, `auto`, `supabase`) |
| `OPENAI_API_KEY` | OpenAI API key |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_KEY` | Supabase API key |
| `QDRANT_URL` | Qdrant server URL |

---
