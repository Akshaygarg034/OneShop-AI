"""Password hashing (Argon2id) and JWT access tokens.

Legacy PBKDF2 hashes from the previous version still verify; callers re-hash
to Argon2 on successful login (see needs_rehash).
"""
from __future__ import annotations

import hashlib
import hmac
import time
from typing import Optional

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.config import get_settings

_hasher = PasswordHasher()
_JWT_ALGORITHM = "HS256"
_LEGACY_PREFIX = "pbkdf2_sha256$"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, stored: str) -> bool:
    # Google-only accounts are stored with an empty hash; they have no password
    # login path and must never be reachable through this function.
    if not stored:
        return False
    if stored.startswith(_LEGACY_PREFIX):
        return _verify_legacy(password, stored)
    try:
        return _hasher.verify(stored, password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def needs_rehash(stored: str) -> bool:
    return stored.startswith(_LEGACY_PREFIX) or _hasher.check_needs_rehash(stored)


def _verify_legacy(password: str, stored: str) -> bool:
    try:
        _, iterations, salt, digest_hex = stored.split("$")
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations))
        return hmac.compare_digest(candidate.hex(), digest_hex)
    except (ValueError, AttributeError):
        return False


def issue_token(user_id: str) -> str:
    settings = get_settings()
    now = int(time.time())
    return jwt.encode(
        {"sub": user_id, "iat": now, "exp": now + settings.auth_token_ttl_seconds},
        settings.auth_secret,
        algorithm=_JWT_ALGORITHM,
    )


def verify_token(token: str) -> Optional[str]:
    """Return the user_id for a valid, unexpired token; None otherwise."""
    try:
        payload = jwt.decode(token, get_settings().auth_secret, algorithms=[_JWT_ALGORITHM])
        return payload.get("sub")
    except jwt.InvalidTokenError:
        return None
