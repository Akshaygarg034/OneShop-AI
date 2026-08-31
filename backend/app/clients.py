"""Shared async clients (OpenAI, Qdrant, Supabase), created once at startup."""
from __future__ import annotations

import logging
from typing import Optional

from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient

from app.config import get_settings

logger = logging.getLogger(__name__)

_openai: Optional[AsyncOpenAI] = None
_qdrant: Optional[AsyncQdrantClient] = None
_supabase = None  # supabase.AsyncClient


async def init_clients() -> None:
    global _openai, _qdrant, _supabase
    settings = get_settings()

    _openai = AsyncOpenAI(api_key=settings.openai_api_key)
    _qdrant = AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)

    if settings.uses_supabase:
        from supabase import acreate_client

        _supabase = await acreate_client(settings.supabase_url, settings.supabase_key)


async def close_clients() -> None:
    global _openai, _qdrant, _supabase
    if _openai is not None:
        await _openai.close()
    if _qdrant is not None:
        await _qdrant.close()
    _openai = _qdrant = _supabase = None


def openai_client() -> AsyncOpenAI:
    if _openai is None:
        raise RuntimeError("clients not initialized — init_clients() must run at startup")
    return _openai


def qdrant_client() -> AsyncQdrantClient:
    if _qdrant is None:
        raise RuntimeError("clients not initialized — init_clients() must run at startup")
    return _qdrant


def supabase_client():
    if _supabase is None:
        raise RuntimeError("Supabase client not initialized (STORAGE_BACKEND=memory or startup skipped)")
    return _supabase


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed texts with the configured OpenAI embedding model."""
    settings = get_settings()
    resp = await openai_client().embeddings.create(
        model=settings.embed_model,
        input=texts,
        dimensions=settings.embed_dimensions,
    )
    return [item.embedding for item in resp.data]
