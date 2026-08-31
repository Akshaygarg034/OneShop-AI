"""Preference-profile endpoints: see what the assistant has learned, and edit it."""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.auth.deps import assert_session_owner
from app.preferences.models import Preferences
from app.preferences.store import preference_store

router = APIRouter(tags=["profile"])

_CLEARABLE = ("budget", "brands", "categories", "features", "attributes", "rejected_products")


class ProfileResponse(BaseModel):
    session_id: str
    profile: Preferences


class ProfileUpdate(BaseModel):
    clear: Optional[Literal["all", "budget", "brands", "categories", "features",
                            "attributes", "rejected_products"]] = None
    remove_key: Optional[str] = None  # with a section in `clear`, removes one entry instead


@router.get("/session/profile", response_model=ProfileResponse)
async def get_profile(session_id: str, authorization: str = Header(default="")) -> ProfileResponse:
    assert_session_owner(session_id, authorization)
    prefs = await preference_store().get(session_id)
    return ProfileResponse(session_id=session_id, profile=prefs)


@router.patch("/session/profile", response_model=ProfileResponse)
async def update_profile(
    session_id: str, update: ProfileUpdate, authorization: str = Header(default="")
) -> ProfileResponse:
    assert_session_owner(session_id, authorization)
    if update.clear is None:
        raise HTTPException(status_code=400, detail="nothing to update")

    store = preference_store()
    prefs = await store.get(session_id)

    if update.clear == "all":
        prefs = Preferences()
    elif update.clear == "budget":
        if update.remove_key:
            prefs.budgets.pop(update.remove_key.strip().lower(), None)
        else:
            prefs.budgets = {}
    elif update.remove_key:
        section = getattr(prefs, update.clear)
        section.pop(update.remove_key.strip().lower(), None)
    else:
        setattr(prefs, update.clear, {})

    await store.save(session_id, prefs)
    return ProfileResponse(session_id=session_id, profile=prefs)
