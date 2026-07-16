"""
Security utilities: JWT token creation/verification, password hashing.

All cryptographic operations are centralised here to ensure consistent
algorithm choices and to make future rotation straightforward.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """Return bcrypt hash of the given plain-text password."""
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True if plain_password matches the bcrypt hash."""
    return _pwd_context.verify(plain_password, hashed_password)


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

class TokenType:
    ACCESS = "access"
    REFRESH = "refresh"


def create_access_token(
    subject: str,
    secret_key: str,
    algorithm: str = "HS256",
    expires_minutes: int = 60,
    additional_claims: dict[str, Any] | None = None,
) -> str:
    """
    Create a signed JWT access token.

    Args:
        subject: Token subject, typically the user ID or username.
        secret_key: JWT signing secret.
        algorithm: JWT algorithm (HS256 recommended for symmetric keys).
        expires_minutes: Token lifetime in minutes.
        additional_claims: Extra claims to embed in the token payload.

    Returns:
        Encoded JWT string.
    """
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
        "type": TokenType.ACCESS,
    }
    if additional_claims:
        payload.update(additional_claims)

    token = jwt.encode(payload, secret_key, algorithm=algorithm)
    logger.debug("Access token created", subject=subject, expires_minutes=expires_minutes)
    return token


def create_refresh_token(
    subject: str,
    secret_key: str,
    algorithm: str = "HS256",
    expires_days: int = 7,
) -> str:
    """
    Create a signed JWT refresh token.

    Args:
        subject: Token subject, typically the user ID.
        secret_key: JWT signing secret.
        algorithm: JWT algorithm.
        expires_days: Refresh token lifetime in days.

    Returns:
        Encoded JWT string.
    """
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(days=expires_days),
        "type": TokenType.REFRESH,
    }
    return jwt.encode(payload, secret_key, algorithm=algorithm)


def decode_token(
    token: str,
    secret_key: str,
    algorithm: str = "HS256",
    expected_type: str = TokenType.ACCESS,
) -> dict[str, Any]:
    """
    Decode and validate a JWT token.

    Args:
        token: Encoded JWT string.
        secret_key: JWT signing secret used to verify the signature.
        algorithm: JWT algorithm.
        expected_type: Expected token type ("access" or "refresh").

    Returns:
        Decoded payload dictionary.

    Raises:
        ValueError: If the token is invalid, expired, or of the wrong type.
    """
    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
    except JWTError as exc:
        logger.warning("JWT decode failure", error=str(exc))
        raise ValueError(f"Invalid or expired token: {exc}") from exc

    if payload.get("type") != expected_type:
        raise ValueError(
            f"Expected token type '{expected_type}', got '{payload.get('type')}'"
        )

    return payload
