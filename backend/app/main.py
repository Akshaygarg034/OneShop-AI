"""
FastAPI entry point. SHARED - thin, rarely touched.
Each person's router is included here.

Run (mock mode, no API keys needed):
    cd backend
    pip install -r requirements.txt        # or just: pip install fastapi uvicorn pydantic python-dotenv
    uvicorn app.main:app --reload
Then open http://localhost:8000/docs
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, cart, catalog, chat
from app.config import RAG_ENABLED

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-load the embedding model at startup so the first query isn't slow.
    if RAG_ENABLED:
        try:
            from app.rag.retriever import _vector_store
            logger.info("startup: pre-loading embedding model...")
            _vector_store()
            logger.info("startup: embedding model ready.")
        except Exception as exc:
            logger.warning("startup: could not pre-load embedding model - %s", exc)
    yield


app = FastAPI(title="Telekom Smart Shopping Assistant", lifespan=lifespan)

# Allow the React frontend to call us. Both 5173 (Vite's own default) and 5180
# (this repo's .claude/launch.json dev port) are listed - they'd drifted out
# of sync, which silently broke every fetch when running via launch.json.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5180",
        "http://127.0.0.1:5180",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(cart.router)
app.include_router(catalog.router)
app.include_router(auth.router)


@app.get("/health")
def health():
    return {"status": "ok"}
