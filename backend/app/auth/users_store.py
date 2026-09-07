"""User account persistence (Supabase `users` table; in-memory for tests)."""
from __future__ import annotations

import logging
import uuid
from typing import Optional

from app.config import get_settings

logger = logging.getLogger(__name__)

_TABLE = "users"


class MemoryUserBackend:
    def __init__(self) -> None:
        self._by_id: dict[str, dict] = {}
        self._email_index: dict[str, str] = {}
        self._google_index: dict[str, str] = {}

    async def get_by_email(self, email: str) -> Optional[dict]:
        user_id = self._email_index.get(email.lower())
        return dict(self._by_id[user_id]) if user_id else None

    async def get_by_id(self, user_id: str) -> Optional[dict]:
        record = self._by_id.get(user_id)
        return dict(record) if record else None

    async def get_by_google_sub(self, google_sub: str) -> Optional[dict]:
        user_id = self._google_index.get(google_sub)
        return dict(self._by_id[user_id]) if user_id else None

    async def create(self, email: str, password_hash: str, name: str = "",
                     phone: str = "", google_sub: str = "") -> dict:
        email = email.lower()
        if email in self._email_index:
            raise ValueError("an account with this email already exists")
        user_id = str(uuid.uuid4())
        record = {"user_id": user_id, "email": email, "password_hash": password_hash,
                  "name": name, "phone": phone, "google_sub": google_sub}
        self._by_id[user_id] = record
        self._email_index[email] = user_id
        if google_sub:
            self._google_index[google_sub] = user_id
        return dict(record)

    async def link_google_sub(self, user_id: str, google_sub: str) -> None:
        if user_id in self._by_id:
            self._by_id[user_id]["google_sub"] = google_sub
            self._google_index[google_sub] = user_id

    async def update_password_hash(self, user_id: str, password_hash: str) -> None:
        if user_id in self._by_id:
            self._by_id[user_id]["password_hash"] = password_hash


class SupabaseUserBackend:
    """Maps the DB columns (id / full_name) to the canonical dict (user_id / name)."""

    @staticmethod
    def _to_record(row: dict) -> dict:
        return {
            "user_id": row["id"],
            "email": row.get("email", ""),
            "password_hash": row.get("password_hash", ""),
            "name": row.get("full_name") or "",
            "phone": row.get("phone") or "",
            "google_sub": row.get("google_sub") or "",
        }

    async def get_by_email(self, email: str) -> Optional[dict]:
        from app.clients import supabase_client

        resp = await (
            supabase_client().table(_TABLE)
            .select("*").eq("email", email.lower()).limit(1).execute()
        )
        return self._to_record(resp.data[0]) if resp.data else None

    async def get_by_id(self, user_id: str) -> Optional[dict]:
        from app.clients import supabase_client

        resp = await (
            supabase_client().table(_TABLE)
            .select("*").eq("id", user_id).limit(1).execute()
        )
        return self._to_record(resp.data[0]) if resp.data else None

    async def get_by_google_sub(self, google_sub: str) -> Optional[dict]:
        from app.clients import supabase_client

        resp = await (
            supabase_client().table(_TABLE)
            .select("*").eq("google_sub", google_sub).limit(1).execute()
        )
        return self._to_record(resp.data[0]) if resp.data else None

    async def create(self, email: str, password_hash: str, name: str = "",
                     phone: str = "", google_sub: str = "") -> dict:
        from app.clients import supabase_client

        email = email.lower()
        if await self.get_by_email(email):
            raise ValueError("an account with this email already exists")
        user_id = str(uuid.uuid4())
        await supabase_client().table(_TABLE).insert({
            "id": user_id, "email": email, "password_hash": password_hash,
            "full_name": name, "phone": phone, "google_sub": google_sub or None,
        }).execute()
        return {"user_id": user_id, "email": email, "password_hash": password_hash,
                "name": name, "phone": phone, "google_sub": google_sub}

    async def link_google_sub(self, user_id: str, google_sub: str) -> None:
        from app.clients import supabase_client

        await supabase_client().table(_TABLE).update(
            {"google_sub": google_sub}
        ).eq("id", user_id).execute()

    async def update_password_hash(self, user_id: str, password_hash: str) -> None:
        from app.clients import supabase_client

        await supabase_client().table(_TABLE).update(
            {"password_hash": password_hash}
        ).eq("id", user_id).execute()


_store = None


def user_store():
    global _store
    if _store is None:
        _store = SupabaseUserBackend() if get_settings().uses_supabase else MemoryUserBackend()
    return _store
