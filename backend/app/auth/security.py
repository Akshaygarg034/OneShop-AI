"""
Password hashing + token issuance. Owned by P4.

Stdlib only (hashlib/hmac/secrets) - no bcrypt/PyJWT dependency, so it installs
instantly and never needs a native build. PBKDF2-SHA256 with 100k iterations is
a NIST-recommended KDF; plenty for a hackathon POC's auth.

Tokens are self-contained and hmac-signed: "<user_id>.<expiry>.<signature>",
base64url-encoded. Verifying a token needs no server-side lookup/storage - just
recompute the signature with AUTH_SECRET and check the expiry.
"""
import base64
import hashlib
import hmac
import secrets
import time

from app.config import AUTH_SECRET, AUTH_TOKEN_TTL_SECONDS

_PBKDF2_ITERATIONS = 100_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), _PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, iterations, salt, digest_hex = stored.split("$")
        if scheme != "pbkdf2_sha256":
            return False
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations))
        return hmac.compare_digest(candidate.hex(), digest_hex)
    except (ValueError, AttributeError):
        return False


def _sign(payload: str) -> str:
    return hmac.new(AUTH_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()


def issue_token(user_id: str) -> str:
    expiry = int(time.time()) + AUTH_TOKEN_TTL_SECONDS
    payload = f"{user_id}.{expiry}"
    token = f"{payload}.{_sign(payload)}"
    return base64.urlsafe_b64encode(token.encode()).decode().rstrip("=")


def verify_token(token: str) -> str | None:
    """Return the user_id if the token is well-formed, correctly signed, and
    unexpired. Otherwise None - callers treat that as unauthenticated."""
    try:
        padded = token + "=" * (-len(token) % 4)
        decoded = base64.urlsafe_b64decode(padded.encode()).decode()
        user_id, expiry, signature = decoded.rsplit(".", 2)
    except (ValueError, UnicodeDecodeError, base64.binascii.Error):
        return None

    payload = f"{user_id}.{expiry}"
    if not hmac.compare_digest(_sign(payload), signature):
        return None
    if int(expiry) < int(time.time()):
        return None
    return user_id
