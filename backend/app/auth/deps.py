"""Session ownership checks.

- A "guest-" session id is an anonymous capability: holding it grants access.
- A logged-in session id equals the account's user_id, so any read OR write
  against it requires a bearer token proving the caller is that user.
- Session ids that are neither guest-prefixed nor a known-format user id are
  rejected, closing the "mint an arbitrary non-guest session" hole.
"""
from fastapi import Header, HTTPException

from app.auth.security import verify_token

_GUEST_PREFIX = "guest-"


def assert_session_owner(session_id: str, authorization: str) -> None:
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    if session_id.startswith(_GUEST_PREFIX):
        return
    token = authorization.removeprefix("Bearer ").strip()
    user_id = verify_token(token) if token else None
    if user_id != session_id:
        raise HTTPException(status_code=401, detail="not authorized for this session")


async def session_owner_header(authorization: str = Header(default="")) -> str:
    """FastAPI dependency that just forwards the Authorization header value."""
    return authorization
