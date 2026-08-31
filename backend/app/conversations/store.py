"""Conversation and message persistence.

One row per message (append-only) instead of a single ever-growing JSONB blob:
turns are O(1) to write, histories are paginated reads, and rolling summaries
keep prompt sizes bounded no matter how long a conversation gets.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field

from app.config import get_settings

logger = logging.getLogger(__name__)

_CONVERSATIONS = "conversations"
_MESSAGES = "messages"


class Message(BaseModel):
    conversation_id: str
    session_id: str
    seq: int
    role: str
    content: str
    recommendations: list[dict] = Field(default_factory=list)
    created_at: str = ""


class ConversationMeta(BaseModel):
    id: str
    session_id: str
    title: str = ""
    summary: str = ""
    summary_upto_seq: int = 0
    message_count: int = 0
    updated_at: str = ""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class MemoryConversationStore:
    def __init__(self) -> None:
        self._meta: dict[str, ConversationMeta] = {}
        self._messages: dict[str, list[Message]] = {}

    async def get_meta(self, conversation_id: str) -> Optional[ConversationMeta]:
        return self._meta.get(conversation_id)

    async def append(self, session_id: str, conversation_id: str, role: str,
                     content: str, recommendations: list[dict] | None = None) -> Message:
        meta = self._meta.get(conversation_id)
        if meta is None:
            meta = ConversationMeta(id=conversation_id, session_id=session_id)
            self._meta[conversation_id] = meta
            self._messages[conversation_id] = []
        if not meta.title and role == "user":
            meta.title = content[:80]
        meta.updated_at = _now_iso()
        meta.message_count += 1
        msg = Message(
            conversation_id=conversation_id, session_id=session_id,
            seq=meta.message_count, role=role, content=content,
            recommendations=recommendations or [], created_at=_now_iso(),
        )
        self._messages[conversation_id].append(msg)
        return msg

    async def recent(self, conversation_id: str, limit: int) -> list[Message]:
        return self._messages.get(conversation_id, [])[-limit:]

    async def full_history(self, conversation_id: str) -> list[Message]:
        return list(self._messages.get(conversation_id, []))

    async def list_ids(self, session_id: str) -> list[str]:
        return [m.id for m in self._meta.values() if m.session_id == session_id]

    async def list_meta(self, session_id: str) -> list[ConversationMeta]:
        metas = [m for m in self._meta.values() if m.session_id == session_id]
        return sorted(metas, key=lambda m: m.updated_at, reverse=True)

    async def latest_id(self, session_id: str) -> Optional[str]:
        ids = await self.list_ids(session_id)
        return ids[-1] if ids else None

    async def delete(self, session_id: str, conversation_id: str) -> None:
        meta = self._meta.get(conversation_id)
        if meta and meta.session_id == session_id:
            self._meta.pop(conversation_id, None)
            self._messages.pop(conversation_id, None)

    async def set_summary(self, conversation_id: str, summary: str, upto_seq: int) -> None:
        meta = self._meta.get(conversation_id)
        if meta:
            meta.summary = summary
            meta.summary_upto_seq = upto_seq

    async def reassign_session(self, old_session_id: str, new_session_id: str) -> None:
        for meta in self._meta.values():
            if meta.session_id == old_session_id:
                meta.session_id = new_session_id
        for messages in self._messages.values():
            for m in messages:
                if m.session_id == old_session_id:
                    m.session_id = new_session_id


class SupabaseConversationStore:
    async def get_meta(self, conversation_id: str) -> Optional[ConversationMeta]:
        from app.clients import supabase_client

        resp = await (
            supabase_client().table(_CONVERSATIONS)
            .select("*").eq("id", conversation_id).limit(1).execute()
        )
        if not resp.data:
            return None
        row = resp.data[0]
        return ConversationMeta(
            id=row["id"], session_id=row["session_id"], title=row.get("title") or "",
            summary=row.get("summary") or "", summary_upto_seq=row.get("summary_upto_seq") or 0,
            message_count=row.get("message_count") or 0, updated_at=row.get("updated_at") or "",
        )

    async def append(self, session_id: str, conversation_id: str, role: str,
                     content: str, recommendations: list[dict] | None = None) -> Message:
        from app.clients import supabase_client

        client = supabase_client()
        meta = await self.get_meta(conversation_id)
        if meta is None:
            title = content[:80] if role == "user" else ""
            await client.table(_CONVERSATIONS).upsert(
                {"id": conversation_id, "session_id": session_id, "title": title, "message_count": 0},
                on_conflict="id",
            ).execute()
            seq = 1
        else:
            seq = meta.message_count + 1

        msg = Message(
            conversation_id=conversation_id, session_id=session_id, seq=seq,
            role=role, content=content, recommendations=recommendations or [],
            created_at=_now_iso(),
        )
        await client.table(_MESSAGES).insert({
            "conversation_id": conversation_id, "session_id": session_id, "seq": seq,
            "role": role, "content": content, "recommendations": msg.recommendations,
            "created_at": msg.created_at,
        }).execute()
        await client.table(_CONVERSATIONS).update(
            {"message_count": seq, "updated_at": msg.created_at}
        ).eq("id", conversation_id).execute()
        return msg

    async def recent(self, conversation_id: str, limit: int) -> list[Message]:
        from app.clients import supabase_client

        resp = await (
            supabase_client().table(_MESSAGES)
            .select("*").eq("conversation_id", conversation_id)
            .order("seq", desc=True).limit(limit).execute()
        )
        return [Message(**row) for row in reversed(resp.data or [])]

    async def full_history(self, conversation_id: str) -> list[Message]:
        from app.clients import supabase_client

        resp = await (
            supabase_client().table(_MESSAGES)
            .select("*").eq("conversation_id", conversation_id)
            .order("seq", desc=False).execute()
        )
        return [Message(**row) for row in resp.data or []]

    async def list_ids(self, session_id: str) -> list[str]:
        from app.clients import supabase_client

        resp = await (
            supabase_client().table(_CONVERSATIONS)
            .select("id").eq("session_id", session_id)
            .order("updated_at", desc=False).execute()
        )
        return [row["id"] for row in resp.data or []]

    async def list_meta(self, session_id: str) -> list[ConversationMeta]:
        from app.clients import supabase_client

        resp = await (
            supabase_client().table(_CONVERSATIONS)
            .select("id,session_id,title,updated_at").eq("session_id", session_id)
            .order("updated_at", desc=True).execute()
        )
        return [
            ConversationMeta(
                id=row["id"], session_id=row["session_id"],
                title=row.get("title") or "", updated_at=row.get("updated_at") or "",
            )
            for row in resp.data or []
        ]

    async def latest_id(self, session_id: str) -> Optional[str]:
        ids = await self.list_ids(session_id)
        return ids[-1] if ids else None

    async def delete(self, session_id: str, conversation_id: str) -> None:
        from app.clients import supabase_client

        client = supabase_client()
        await client.table(_MESSAGES).delete().eq("conversation_id", conversation_id).eq(
            "session_id", session_id).execute()
        await client.table(_CONVERSATIONS).delete().eq("id", conversation_id).eq(
            "session_id", session_id).execute()

    async def set_summary(self, conversation_id: str, summary: str, upto_seq: int) -> None:
        from app.clients import supabase_client

        await supabase_client().table(_CONVERSATIONS).update(
            {"summary": summary, "summary_upto_seq": upto_seq}
        ).eq("id", conversation_id).execute()

    async def reassign_session(self, old_session_id: str, new_session_id: str) -> None:
        from app.clients import supabase_client

        client = supabase_client()
        await client.table(_CONVERSATIONS).update({"session_id": new_session_id}).eq(
            "session_id", old_session_id).execute()
        await client.table(_MESSAGES).update({"session_id": new_session_id}).eq(
            "session_id", old_session_id).execute()


_store = None


def conversation_store():
    global _store
    if _store is None:
        _store = SupabaseConversationStore() if get_settings().uses_supabase else MemoryConversationStore()
    return _store
