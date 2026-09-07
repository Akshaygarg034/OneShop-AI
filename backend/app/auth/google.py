"""Google Sign-In verification.

The browser runs Google Identity Services and receives a signed ID token
(a JWT). It posts that token here; we verify it against Google's published
signing keys and trust only the claims inside. No client secret and no
redirect round trip are involved, which keeps the SPA flow to a single call.

Only `GOOGLE_CLIENT_ID` is needed, and it is safe to expose to the browser —
the audience check is what binds a token to this application.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

import jwt
from jwt import PyJWKClient

from app.config import get_settings

logger = logging.getLogger(__name__)

_CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs"
_VALID_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}

_jwks_client: Optional[PyJWKClient] = None


class GoogleAuthError(Exception):
    """Raised when a credential can't be trusted. The message is user-facing."""


def _client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        # Google rotates signing keys slowly; caching them avoids a fetch per login.
        _jwks_client = PyJWKClient(_CERTS_URL, cache_keys=True, lifespan=3600)
    return _jwks_client


def _decode(credential: str, client_id: str) -> dict:
    """Blocking verification: signature, audience, expiry, required claims."""
    signing_key = _client().get_signing_key_from_jwt(credential)
    return jwt.decode(
        credential,
        signing_key.key,
        algorithms=["RS256"],
        audience=client_id,
        options={"require": ["exp", "iat", "aud", "iss", "sub"]},
    )


async def verify_google_credential(credential: str) -> dict:
    """Return {sub, email, name} for a valid Google ID token."""
    settings = get_settings()
    if not settings.google_client_id:
        raise GoogleAuthError("Google sign-in is not configured on this server.")

    try:
        # PyJWKClient fetches keys over blocking urllib — keep it off the event loop.
        claims = await asyncio.to_thread(_decode, credential, settings.google_client_id)
    except Exception as e:
        logger.warning("google: ID token rejected (%s)", e)
        raise GoogleAuthError("Google sign-in failed. Please try again.") from e

    # Checked explicitly rather than via jwt.decode(issuer=...), which only
    # accepts a single value while Google legitimately uses two.
    if claims.get("iss") not in _VALID_ISSUERS:
        raise GoogleAuthError("Google sign-in failed. Please try again.")

    email = (claims.get("email") or "").strip().lower()
    if not email:
        raise GoogleAuthError("That Google account has no email address.")
    if not claims.get("email_verified"):
        # Without this an attacker could claim an unverified address that
        # belongs to somebody else's existing password account.
        raise GoogleAuthError("Your Google email address is not verified.")

    return {"sub": claims["sub"], "email": email, "name": (claims.get("name") or "").strip()}
