"""
FastAPI entry point. SHARED - thin, rarely touched.
Each person's router is included here.

Run (mock mode, no API keys needed):
    cd backend
    pip install -r requirements.txt        # or just: pip install fastapi uvicorn pydantic python-dotenv
    uvicorn app.main:app --reload
Then open http://localhost:8000/docs
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import cart, catalog, chat

app = FastAPI(title="Telekom Smart Shopping Assistant")

# Allow the React frontend (Vite default port) to call us.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # fine for a hackathon POC
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(cart.router)
app.include_router(catalog.router)


@app.get("/health")
def health():
    return {"status": "ok"}
