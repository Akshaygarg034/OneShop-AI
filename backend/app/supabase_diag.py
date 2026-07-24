"""
Shared diagnostics for Supabase connection failures. SHARED (used by both
app/auth/users_store.py and app/session/store.py - same failure modes, same
fix: check SUPABASE_URL/SUPABASE_KEY in backend/.env).
"""
from __future__ import annotations


def describe_supabase_error(e: Exception, url: str) -> str:
    """Turn a raw supabase-py/postgrest exception into an actionable message.

    The most common failure is pasting the Postgres connection password (from
    a `psycopg2`-style DB_CONFIG) into SUPABASE_KEY - that's a different
    credential entirely. SUPABASE_KEY must be the service_role API key from
    the Supabase dashboard -> Settings -> API -> Project API keys.
    """
    text = str(e)
    lowered = text.lower()

    if not url.startswith("https://") or ".supabase.co" not in url:
        return (
            f"SUPABASE_URL looks wrong ({url or '<empty>'}) - it should be the "
            f"project URL, e.g. https://<project-ref>.supabase.co ({text})"
        )
    if "invalid api key" in lowered or "401" in lowered or "unauthorized" in lowered or "jwt" in lowered:
        return (
            f"SUPABASE_KEY was rejected (401/invalid API key) - make sure it's the "
            f"service_role key from Settings -> API, NOT the database password ({text})"
        )
    if (
        "pgrst205" in lowered
        or "could not find the table" in lowered
        or ("relation" in lowered and "does not exist" in lowered)
    ):
        return (
            f"table missing - run the *_schema.sql files in the Supabase SQL editor "
            f"(app/auth/supabase_schema.sql, app/session/supabase_schema.sql) ({text})"
        )
    if "42703" in lowered or ("column" in lowered and "does not exist" in lowered):
        return (
            f"table schema mismatch - a column the code expects is missing; align the "
            f"table with the *_schema.sql files (or the backend's column mapping) ({text})"
        )
    if "getaddrinfo" in lowered or "connection" in lowered or "timed out" in lowered:
        return f"could not reach {url} - check SUPABASE_URL and your network ({text})"
    return text
