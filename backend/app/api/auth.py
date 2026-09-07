"""Auth endpoints. On register/login a guest session's cart, preferences, and
conversations are merged into the account identity (session_id becomes user_id)."""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, EmailStr

from app.auth.google import GoogleAuthError, verify_google_credential
from app.auth.security import hash_password, issue_token, needs_rehash, verify_password, verify_token
from app.auth.users_store import user_store
from app.rate_limit import limiter
from app.session.store import session_store

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str = ""
    phone: str = ""
    session_id: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    session_id: str | None = None


class GoogleRequest(BaseModel):
    """`credential` is the ID token returned by Google Identity Services."""
    credential: str
    session_id: str | None = None


class AuthResponse(BaseModel):
    user_id: str
    email: str
    name: str
    token: str


@router.post("/register", response_model=AuthResponse)
@limiter.limit("5/minute")
async def register(req: RegisterRequest, request: Request) -> AuthResponse:
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="password must be at least 8 characters")
    try:
        user = await user_store().create(req.email, hash_password(req.password), req.name, req.phone)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    if req.session_id:
        await session_store().merge_guest_into_user(req.session_id, user["user_id"])

    return AuthResponse(
        user_id=user["user_id"], email=user["email"], name=user["name"],
        token=issue_token(user["user_id"]),
    )


@router.post("/login", response_model=AuthResponse)
@limiter.limit("10/minute")
async def login(req: LoginRequest, request: Request) -> AuthResponse:
    user = await user_store().get_by_email(req.email)
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="invalid email or password")

    if needs_rehash(user["password_hash"]):
        await user_store().update_password_hash(user["user_id"], hash_password(req.password))

    if req.session_id:
        await session_store().merge_guest_into_user(req.session_id, user["user_id"])

    return AuthResponse(
        user_id=user["user_id"], email=user["email"], name=user["name"],
        token=issue_token(user["user_id"]),
    )


@router.post("/google", response_model=AuthResponse)
@limiter.limit("10/minute")
async def google_login(req: GoogleRequest, request: Request) -> AuthResponse:
    """Sign in (or sign up) with a verified Google account.

    Resolution order is Google id first, then email. Matching on the Google
    `sub` keeps the link stable if the person later changes their Gmail
    address; falling back to email lets an existing password account adopt
    Google sign-in without creating a duplicate.
    """
    try:
        profile = await verify_google_credential(req.credential)
    except GoogleAuthError as e:
        raise HTTPException(status_code=401, detail=str(e))

    store = user_store()
    user = await store.get_by_google_sub(profile["sub"])
    if user is None:
        user = await store.get_by_email(profile["email"])
        if user is not None:
            # Google has already verified they own this address, so attaching
            # it to the existing account is safe and avoids a duplicate.
            await store.link_google_sub(user["user_id"], profile["sub"])
        else:
            # No password hash: this account can only ever sign in via Google.
            user = await store.create(
                profile["email"], "", profile["name"], google_sub=profile["sub"],
            )

    if req.session_id:
        await session_store().merge_guest_into_user(req.session_id, user["user_id"])

    return AuthResponse(
        user_id=user["user_id"], email=user["email"], name=user["name"],
        token=issue_token(user["user_id"]),
    )


@router.get("/me", response_model=AuthResponse)
async def me(authorization: str = Header(default="")) -> AuthResponse:
    token = authorization.removeprefix("Bearer ").strip()
    user_id = verify_token(token) if token else None
    if not user_id:
        raise HTTPException(status_code=401, detail="missing or invalid token")
    user = await user_store().get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    return AuthResponse(user_id=user["user_id"], email=user["email"], name=user["name"], token=token)
