"""Password hashing and JWT token handling for auth.

Uses pbkdf2_hmac (built-in hashlib) for password hashing and PyJWT for tokens.
"""

import hashlib
import hmac
import os
from datetime import UTC, datetime, timedelta

from jwt import InvalidTokenError
from jwt import decode as jwt_decode
from jwt import encode as jwt_encode

from app.core.config import get_settings

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8  # 8 hours
PBKDF2_ITERATIONS = 600_000


def hash_password(password: str) -> str:
    """Hash a password using pbkdf2_hmac with a random salt."""
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"{PBKDF2_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(plain: str, hashed: str | None) -> bool:
    """Verify a plain password against a hash string created by hash_password."""
    if not hashed:
        return False
    try:
        iterations_str, salt_hex, dk_hex = hashed.split("$", 2)
        iterations = int(iterations_str)
        salt = bytes.fromhex(salt_hex)
        dk = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(dk.hex(), dk_hex)
    except (ValueError, TypeError):
        return False


def create_token(user_id: str, auth_version: int) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "auth_version": auth_version,
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt_encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, object] | None:
    settings = get_settings()
    try:
        return jwt_decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except InvalidTokenError:
        return None
