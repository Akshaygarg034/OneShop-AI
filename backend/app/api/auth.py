"""
Auth endpoints. Owned by P4.

user_id is the durable, unique identifier for a customer, stored alongside their
credentials in Supabase (or in-memory in mock mode). On register/login, if the
caller was already browsing as a guest (session_id), that guest session's
history/profile/cart is merged into the session keyed by user_id - the frontend
then switches to using user_id as its session_id, so nothing is lost and every
future request from any device continues the SAME identity.
"""
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, EmailStr

from app.auth.security import hash_password, issue_token, verify_password, verify_token
from app.auth.users_store import users
from app.session.store import store

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str = ""
    phone: str = ""
    session_id: str | None = None   # the guest session to merge in, if any


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    session_id: str | None = None


class AuthResponse(BaseModel):
    user_id: str
    email: str
    name: str
    token: str


@router.post("/register", response_model=AuthResponse)
def register(req: RegisterRequest) -> AuthResponse:
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="password must be at least 8 characters")
    try:
        user = users.create(req.email, hash_password(req.password), req.name, req.phone)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    if req.session_id:
        store.merge_guest_into_user(req.session_id, user["user_id"])

    return AuthResponse(
        user_id=user["user_id"], email=user["email"], name=user["name"],
        token=issue_token(user["user_id"]),
    )


@router.post("/login", response_model=AuthResponse)
def login(req: LoginRequest) -> AuthResponse:
    user = users.get_by_email(req.email)
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="invalid email or password")

    if req.session_id:
        store.merge_guest_into_user(req.session_id, user["user_id"])

    return AuthResponse(
        user_id=user["user_id"], email=user["email"], name=user["name"],
        token=issue_token(user["user_id"]),
    )


@router.get("/me", response_model=AuthResponse)
def me(authorization: str = Header(default="")) -> AuthResponse:
    token = authorization.removeprefix("Bearer ").strip()
    user_id = verify_token(token) if token else None
    if not user_id:
        raise HTTPException(status_code=401, detail="missing or invalid token")
    user = users.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    return AuthResponse(user_id=user["user_id"], email=user["email"], name=user["name"], token=token)
