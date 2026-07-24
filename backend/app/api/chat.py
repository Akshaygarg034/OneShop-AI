"""
/chat endpoint. Owned by P1.
Loads the session, runs the pipeline, returns a ChatResponse.
"""
import uuid

from fastapi import APIRouter

from app.agents.graph import run_pipeline
from app.contracts.models import (
    ChatConversationsResponse,
    ChatHistoryMessage,
    ChatHistoryResponse,
    ChatRequest,
    ChatResponse,
)
from app.session.store import store

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    session = store.get(req.session_id)
    # Use the client-supplied conversation_id or mint a new thread.
    conversation_id = req.conversation_id or str(uuid.uuid4())
    response = run_pipeline(req.message, session, conversation_id)
    store.save(session)  # persist conversations + profile + cart (no-op for in-memory)
    return response


@router.get("/chat/history", response_model=ChatHistoryResponse)
def history(session_id: str, conversation_id: str = "") -> ChatHistoryResponse:
    """Return the message history for a specific conversation thread.
    If conversation_id is omitted the most-recently-active thread is returned,
    which is the right default for a returning user who just wants to continue.
    session_id becomes user_id after login, so history persists across devices."""
    session = store.get(session_id)
    if conversation_id and conversation_id in session.conversations:
        hist = session.conversations[conversation_id]
        conv_id = conversation_id
    elif session.conversations:
        # Most recent thread (dict preserves insertion order in Python 3.7+)
        conv_id = list(session.conversations.keys())[-1]
        hist = session.conversations[conv_id]
    else:
        conv_id = ""
        hist = []

    return ChatHistoryResponse(
        session_id=session_id,
        conversation_id=conv_id,
        history=[
            ChatHistoryMessage(
                role=m["role"],
                content=m["content"],
                recommendations=m.get("recommendations", []),
            )
            for m in hist
        ],
    )


@router.get("/chat/conversations", response_model=ChatConversationsResponse)
def conversations(session_id: str) -> ChatConversationsResponse:
    """List all conversation thread IDs for a session."""
    session = store.get(session_id)
    return ChatConversationsResponse(
        session_id=session_id,
        conversation_ids=list(session.conversations.keys()),
    )
