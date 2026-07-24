"""
Preference-profile endpoint. Owned by P1/P4.

Exposes the personalization the assistant has learned for a session/user, so it's
visible and testable (e.g. watch brands_viewed / rejected grow as you chat, then
see recommendations re-rank). Owner-gated like chat history: reading a logged-in
account's profile requires that user's token.
"""
from fastapi import APIRouter, Header

from app.auth.deps import assert_session_owner
from app.contracts.models import SessionProfileResponse
from app.session.store import store

router = APIRouter(tags=["profile"])


@router.get("/session/profile", response_model=SessionProfileResponse)
def get_profile(session_id: str, authorization: str = Header(default="")) -> SessionProfileResponse:
    assert_session_owner(session_id, authorization)
    session = store.get(session_id)
    return SessionProfileResponse(session_id=session_id, profile=session.profile)
