"""
/chat endpoint. Owned by P1.
Loads the session, runs the pipeline, returns a ChatResponse.
"""
from fastapi import APIRouter

from app.agents.graph import run_pipeline
from app.contracts.models import ChatRequest, ChatResponse
from app.session.store import store

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    session = store.get(req.session_id)
    return run_pipeline(req.message, session)
