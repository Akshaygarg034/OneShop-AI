"""Chat endpoints: blocking JSON, SSE streaming, history, and thread management."""
from __future__ import annotations

import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, Header, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from app.agents.graph import run_turn
from app.auth.deps import assert_session_owner
from app.config import get_settings
from app.contracts.models import (
    ChatConversationsResponse,
    ChatHistoryMessage,
    ChatHistoryResponse,
    ChatRequest,
    ChatResponse,
    ConversationSummary,
)
from app.conversations.store import conversation_store
from app.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


def _assert_chat_allowed(session_id: str, authorization: str) -> None:
    """Chat requires a logged-in account when REQUIRE_LOGIN_FOR_CHAT is on;
    ownership of the session is verified either way."""
    if get_settings().require_login_for_chat and session_id.startswith("guest-"):
        raise HTTPException(status_code=401, detail="Please sign in to chat with the assistant.")
    assert_session_owner(session_id, authorization)


@router.post("/chat", response_model=ChatResponse)
@limiter.limit("30/minute")
async def chat(req: ChatRequest, request: Request, authorization: str = Header(default="")) -> ChatResponse:
    _assert_chat_allowed(req.session_id, authorization)
    conversation_id = req.conversation_id or str(uuid.uuid4())
    return await run_turn(req.session_id, req.message, conversation_id)


@router.post("/chat/stream")
@limiter.limit("30/minute")
async def chat_stream(req: ChatRequest, request: Request, authorization: str = Header(default="")):
    """SSE stream: `token` events with reply deltas, then `recommendations`
    (full product objects — no follow-up catalog fetch needed), `nba`, `done`."""
    _assert_chat_allowed(req.session_id, authorization)
    conversation_id = req.conversation_id or str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue()

    async def on_token(delta: str) -> None:
        await queue.put(("token", {"text": delta}))

    async def run() -> None:
        try:
            response = await run_turn(req.session_id, req.message, conversation_id, stream_handler=on_token)
            await queue.put(("recommendations", {
                "recommendations": [r.model_dump() for r in response.recommendations],
                "products": [p.model_dump() for p in response.products],
            }))
            if response.nba:
                await queue.put(("nba", {"nba": response.nba}))
            await queue.put(("done", {
                "conversation_id": response.conversation_id,
                "reply_text": response.reply_text,
            }))
        except Exception:
            logger.exception("chat_stream: turn failed for session %s", req.session_id)
            await queue.put(("error", {"detail": "Something went wrong — please try again."}))
        finally:
            await queue.put(None)

    task = asyncio.create_task(run())

    async def events():
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                event, payload = item
                yield {"event": event, "data": json.dumps(payload)}
        finally:
            task.cancel()

    return EventSourceResponse(events())


@router.get("/chat/history", response_model=ChatHistoryResponse)
async def history(
    session_id: str, conversation_id: str = "", authorization: str = Header(default="")
) -> ChatHistoryResponse:
    """Message history for one thread; defaults to the most recent thread."""
    assert_session_owner(session_id, authorization)
    store = conversation_store()

    conv_id = conversation_id or (await store.latest_id(session_id)) or ""
    if not conv_id:
        return ChatHistoryResponse(session_id=session_id)

    meta = await store.get_meta(conv_id)
    if meta is None or meta.session_id != session_id:
        return ChatHistoryResponse(session_id=session_id)

    messages = await store.full_history(conv_id)
    return ChatHistoryResponse(
        session_id=session_id,
        conversation_id=conv_id,
        history=[
            ChatHistoryMessage(
                role=m.role, content=m.content,
                recommendations=m.recommendations, created_at=m.created_at,
            )
            for m in messages
        ],
    )


@router.get("/chat/conversations", response_model=ChatConversationsResponse)
async def conversations(session_id: str, authorization: str = Header(default="")) -> ChatConversationsResponse:
    assert_session_owner(session_id, authorization)
    metas = await conversation_store().list_meta(session_id)
    return ChatConversationsResponse(
        session_id=session_id,
        conversation_ids=[m.id for m in metas],
        conversations=[
            ConversationSummary(id=m.id, title=m.title, updated_at=m.updated_at) for m in metas
        ],
    )


@router.delete("/chat/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str, session_id: str, authorization: str = Header(default="")
) -> dict:
    assert_session_owner(session_id, authorization)
    store = conversation_store()
    meta = await store.get_meta(conversation_id)
    if meta is None or meta.session_id != session_id:
        raise HTTPException(status_code=404, detail="conversation not found")
    await store.delete(session_id, conversation_id)
    return {"deleted": conversation_id}
