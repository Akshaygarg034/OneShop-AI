"""
User accounts. Owned by P4.

Same pluggable-backend shape as app/session/store.py: in-memory by default,
Supabase Postgres when configured, always falling back to memory if Supabase is
unset/unreachable so auth can never take the whole app down.

user_id is the durable, unique identifier for a customer. Once a guest logs in
or registers, the frontend switches its session_id to their user_id - the
existing SessionStore (keyed by an opaque string) needs no changes to persist
history/profile/cart under that identity instead of a random guest id.
"""
from __future__ import annotations

import logging
import uuid

from app.config import SESSION_BACKEND, SUPABASE_KEY, SUPABASE_URL
from app.supabase_diag import describe_supabase_error

logger = logging.getLogger(__name__)


class MemoryUserBackend:
    name = "memory"

    def __init__(self):
        self._by_id: dict[str, dict] = {}
        self._email_index: dict[str, str] = {}   # email -> user_id

    def get_by_email(self, email: str) -> dict | None:
        user_id = self._email_index.get(email.lower())
        return self._by_id.get(user_id) if user_id else None

    def get_by_id(self, user_id: str) -> dict | None:
        return self._by_id.get(user_id)

    def create(self, email: str, password_hash: str, name: str = "", phone: str = "") -> dict:
        email = email.lower()
        if email in self._email_index:
            raise ValueError("an account with this email already exists")
        user_id = uuid.uuid4().hex
        record = {"user_id": user_id, "email": email, "password_hash": password_hash,
                  "name": name, "phone": phone}
        self._by_id[user_id] = record
        self._email_index[email] = user_id
        return record


class SupabaseUserBackend:
    """Users persisted as rows in Supabase Postgres (see supabase_schema.sql).

    The physical table uses `id`/`full_name` (a UUID primary key and a single
    name column); the rest of the app speaks in `user_id`/`name`. This backend
    is the ONLY place that mapping lives - `_to_record` translates a DB row into
    the canonical dict everything else consumes, so callers never see the column
    names. Note the table has no `phone` column, so a supplied phone isn't
    persisted (the register form doesn't collect one).
    """
    name = "supabase"

    def __init__(self, url: str, key: str, table: str = "users"):
        from supabase import create_client  # heavy import, kept local
        self._client = create_client(url, key)
        self._table = table
        # Probe a column that actually exists so a schema mismatch fails fast here
        # (and _make_backend can fall back to memory) rather than mid-request.
        self._client.table(self._table).select("id").limit(1).execute()

    @staticmethod
    def _to_record(row: dict) -> dict:
        """DB row (id/full_name/...) -> canonical user dict (user_id/name/...)."""
        return {
            "user_id": row["id"],
            "email": row.get("email", ""),
            "password_hash": row.get("password_hash", ""),
            "name": row.get("full_name", "") or "",
            "phone": "",  # no phone column in this table
        }

    def get_by_email(self, email: str) -> dict | None:
        resp = (
            self._client.table(self._table)
            .select("*")
            .eq("email", email.lower())
            .limit(1)
            .execute()
        )
        return self._to_record(resp.data[0]) if resp.data else None

    def get_by_id(self, user_id: str) -> dict | None:
        resp = (
            self._client.table(self._table)
            .select("*")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )
        return self._to_record(resp.data[0]) if resp.data else None

    def create(self, email: str, password_hash: str, name: str = "", phone: str = "") -> dict:
        email = email.lower()
        if self.get_by_email(email):
            raise ValueError("an account with this email already exists")
        user_id = str(uuid.uuid4())  # dashed form to match the `id` uuid column
        self._client.table(self._table).insert({
            "id": user_id, "email": email, "password_hash": password_hash,
            "full_name": name,
        }).execute()
        return {"user_id": user_id, "email": email, "password_hash": password_hash,
                "name": name, "phone": phone}


def _make_backend():
    want = (SESSION_BACKEND or "auto").strip().lower()  # reuse the same switch as sessions
    use_supabase = want == "supabase" or (want == "auto" and SUPABASE_URL and SUPABASE_KEY)
    if use_supabase:
        if not (SUPABASE_URL and SUPABASE_KEY):
            logger.warning("SESSION_BACKEND=supabase but SUPABASE_URL/KEY missing; using in-memory users.")
            return MemoryUserBackend()
        try:
            backend = SupabaseUserBackend(SUPABASE_URL, SUPABASE_KEY)
            logger.info("auth: using Supabase for user accounts.")
            return backend
        except Exception as e:  # noqa - keep auth from taking the app down
            logger.warning(
                "auth: Supabase unavailable, falling back to in-memory users (accounts won't "
                "survive a restart) - %s",
                describe_supabase_error(e, SUPABASE_URL),
            )
            return MemoryUserBackend()
    return MemoryUserBackend()


class UserStore:
    def __init__(self, backend=None):
        self._backend = backend or _make_backend()

    @property
    def backend_name(self) -> str:
        return getattr(self._backend, "name", "memory")

    def get_by_email(self, email: str) -> dict | None:
        return self._backend.get_by_email(email)

    def get_by_id(self, user_id: str) -> dict | None:
        return self._backend.get_by_id(user_id)

    def create(self, email: str, password_hash: str, name: str = "", phone: str = "") -> dict:
        return self._backend.create(email, password_hash, name, phone)


# Single shared instance for the whole app.
users = UserStore()
