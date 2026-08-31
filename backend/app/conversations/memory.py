"""Long-term conversation memory: semantic recall + rolling summaries.

Recent turns go to the LLM verbatim; older turns are compressed into a rolling
summary; and every message is embedded into Qdrant so relevant moments from any
past conversation can be recalled semantically ("what was that phone you showed
me last week?") without ever growing the prompt.
"""
from __future__ import annotations

import logging
import uuid

from qdrant_client import models as qm

from app.clients import embed_texts, openai_client, qdrant_client
from app.config import get_settings
from app.conversations.store import Message, conversation_store

logger = logging.getLogger(__name__)

_NAMESPACE = uuid.UUID("7c9e5a31-4d2f-4b8a-a6c1-9e8f7d6b5a4c")

_SUMMARY_PROMPT = """You maintain a running summary of a shopping-assistant conversation.
Merge the previous summary with the new messages into a compact factual summary (max 150 words).
Keep: stated preferences (budget, brands, features, colors), products discussed or recommended
(with ids when given), decisions made, and open questions. Drop pleasantries. Output only the summary."""


async def ensure_memory_collection() -> None:
    settings = get_settings()
    client = qdrant_client()
    name = settings.qdrant_memory_collection
    if not await client.collection_exists(name):
        await client.create_collection(
            collection_name=name,
            vectors_config=qm.VectorParams(size=settings.embed_dimensions, distance=qm.Distance.COSINE),
        )
    # Qdrant Cloud requires an index for every filtered field.
    for field in ("session_id", "conversation_id"):
        try:
            await client.create_payload_index(
                collection_name=name, field_name=field, field_schema=qm.PayloadSchemaType.KEYWORD,
            )
        except Exception:
            logger.debug("memory: payload index %s already exists", field)


async def index_message(msg: Message) -> None:
    """Embed one message into the memory collection. Failures are logged, never fatal —
    losing a memory vector must not fail the user's turn."""
    settings = get_settings()
    try:
        vector = (await embed_texts([msg.content[:2000]]))[0]
        await qdrant_client().upsert(
            collection_name=settings.qdrant_memory_collection,
            points=[qm.PointStruct(
                id=str(uuid.uuid5(_NAMESPACE, f"{msg.conversation_id}:{msg.seq}")),
                vector=vector,
                payload={
                    "session_id": msg.session_id,
                    "conversation_id": msg.conversation_id,
                    "seq": msg.seq,
                    "role": msg.role,
                    "content": msg.content[:500],
                },
            )],
        )
    except Exception:
        logger.exception("memory: failed to index message %s:%s", msg.conversation_id, msg.seq)


async def recall(session_id: str, query: str, exclude_conversation_id: str = "") -> list[str]:
    """Top-k relevant snippets from this session's past messages (all threads)."""
    settings = get_settings()
    try:
        vector = (await embed_texts([query]))[0]
        must = [qm.FieldCondition(key="session_id", match=qm.MatchValue(value=session_id))]
        must_not = []
        if exclude_conversation_id:
            must_not.append(qm.FieldCondition(
                key="conversation_id", match=qm.MatchValue(value=exclude_conversation_id)))
        result = await qdrant_client().query_points(
            collection_name=settings.qdrant_memory_collection,
            query=vector,
            query_filter=qm.Filter(must=must, must_not=must_not or None),
            limit=settings.memory_recall_top_k,
            score_threshold=0.35,
            with_payload=True,
        )
        return [
            f"[{pt.payload['role']}] {pt.payload['content']}"
            for pt in result.points if pt.payload
        ]
    except Exception:
        logger.exception("memory: recall failed for session %s", session_id)
        return []


async def reassign_session(old_session_id: str, new_session_id: str) -> None:
    """Re-key memory vectors after a guest→user merge."""
    settings = get_settings()
    try:
        await qdrant_client().set_payload(
            collection_name=settings.qdrant_memory_collection,
            payload={"session_id": new_session_id},
            points=qm.Filter(must=[
                qm.FieldCondition(key="session_id", match=qm.MatchValue(value=old_session_id))
            ]),
        )
    except Exception:
        logger.exception("memory: failed to re-key vectors %s -> %s", old_session_id, new_session_id)


async def update_summary_if_due(conversation_id: str) -> None:
    """Fold older turns into the rolling summary once the un-summarized tail
    exceeds the threshold. Keeps every prompt bounded regardless of length."""
    settings = get_settings()
    store = conversation_store()
    meta = await store.get_meta(conversation_id)
    if meta is None:
        return
    unsummarized = meta.message_count - meta.summary_upto_seq
    if unsummarized <= settings.summary_threshold:
        return

    # Summarize everything except the most recent window (kept verbatim in prompts).
    upto_seq = meta.message_count - settings.history_window
    if upto_seq <= meta.summary_upto_seq:
        return
    messages = await store.full_history(conversation_id)
    to_fold = [m for m in messages if meta.summary_upto_seq < m.seq <= upto_seq]
    if not to_fold:
        return

    transcript = "\n".join(f"{m.role}: {m.content}" for m in to_fold)
    try:
        resp = await openai_client().chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": _SUMMARY_PROMPT},
                {"role": "user", "content": f"Previous summary:\n{meta.summary or '(none)'}\n\nNew messages:\n{transcript}"},
            ],
            temperature=0.0,
            max_tokens=400,
            timeout=30,
        )
        summary = (resp.choices[0].message.content or "").strip()
        if summary:
            await store.set_summary(conversation_id, summary, upto_seq)
            logger.info("memory: summarized %s up to seq %d", conversation_id, upto_seq)
    except Exception:
        logger.exception("memory: summarization failed for %s", conversation_id)
