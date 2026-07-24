"""
Ownership checks for endpoints that expose a session's private data. Owned by P4.

Security model (POC, honest about the trade-off):
  - A "guest-" session id is an anonymous, unguessable capability - holding it is
    access (this is what makes the shareable ?session= omnichannel link work).
  - A logged-in session id IS the user's account id, so reading that session's
    PRIVATE data (conversation history) requires a valid token proving you are
    that user. Otherwise anyone who learned a user_id could read their chats.

At scale you'd issue an opaque per-session token distinct from the user id and
verify it everywhere; here we gate the privacy-sensitive reads.
"""
from fastapi import HTTPException

from app.auth.security import verify_token


def assert_session_owner(session_id: str, authorization: str) -> None:
    """Raise 401 unless the caller may read this session's private data.

    Guest sessions are open; account sessions (session_id == user_id) require a
    bearer token whose user_id matches."""
    if not session_id or session_id.startswith("guest-"):
        return
    token = authorization.removeprefix("Bearer ").strip()
    user_id = verify_token(token) if token else None
    if user_id != session_id:
        raise HTTPException(status_code=401, detail="not authorized to read this session")
