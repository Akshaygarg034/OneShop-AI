"""Persistence for user preferences (Supabase table `user_preferences`)."""
from __future__ import annotations

import logging

from app.config import get_settings
from app.preferences.models import Preferences

logger = logging.getLogger(__name__)

_TABLE = "user_preferences"


class MemoryPreferenceStore:
    def __init__(self) -> None:
        self._prefs: dict[str, Preferences] = {}

    async def get(self, session_id: str) -> Preferences:
        return self._prefs.get(session_id, Preferences()).model_copy(deep=True)

    async def save(self, session_id: str, prefs: Preferences) -> None:
        self._prefs[session_id] = prefs.model_copy(deep=True)

    async def delete(self, session_id: str) -> None:
        self._prefs.pop(session_id, None)


class SupabasePreferenceStore:
    async def get(self, session_id: str) -> Preferences:
        from app.clients import supabase_client

        resp = await (
            supabase_client().table(_TABLE)
            .select("prefs")
            .eq("session_id", session_id)
            .limit(1)
            .execute()
        )
        if resp.data:
            return Preferences(**(resp.data[0].get("prefs") or {}))
        return Preferences()

    async def save(self, session_id: str, prefs: Preferences) -> None:
        from app.clients import supabase_client

        await (
            supabase_client().table(_TABLE)
            .upsert({"session_id": session_id, "prefs": prefs.model_dump()}, on_conflict="session_id")
            .execute()
        )

    async def delete(self, session_id: str) -> None:
        from app.clients import supabase_client

        await supabase_client().table(_TABLE).delete().eq("session_id", session_id).execute()


def _make_store():
    if get_settings().uses_supabase:
        return SupabasePreferenceStore()
    return MemoryPreferenceStore()


_store = None


def preference_store():
    global _store
    if _store is None:
        _store = _make_store()
    return _store
