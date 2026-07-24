"""
/chat endpoint. Owned by P1.
Loads the session, runs the pipeline, returns a ChatResponse.
"""
from fastapi import APIRouter

from app.agents.graph import run_pipeline
from app.contracts.models import ChatHistoryResponse, ChatRequest, ChatResponse
from app.session.store import store

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    session = store.get(req.session_id)
    response = run_pipeline(req.message, session)
    store.save(session)  # persist history + profile + cart (no-op for in-memory)
    return response


@router.get("/chat/history", response_model=ChatHistoryResponse)
def history(session_id: str) -> ChatHistoryResponse:
    """The persisted conversation for a session. Once a guest registers/logs in,
    session_id becomes their user_id (see auth's merge-on-login), so calling this
    with that same id returns their history across logins/devices."""
    session = store.get(session_id)
    return ChatHistoryResponse(session_id=session_id, history=session.history)
