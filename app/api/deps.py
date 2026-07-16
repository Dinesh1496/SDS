"""
FastAPI dependency functions.

Provides reusable Depends() for:
- Database session injection
- Current user extraction from JWT token
- Role-based access control guards
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import decode_token, TokenType
from app.db.session import get_db
from app.models.user import User, UserRole, UserStatus
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

DBSession = Annotated[Session, Depends(get_db)]


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: DBSession,
) -> User:
    """
    Extract and validate the current user from the Bearer JWT token.

    Raises:
        HTTPException 401: If the token is invalid or expired.
        HTTPException 403: If the user account is inactive or locked.
    """
    security_cfg = settings.get_security_settings()
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_token(
            token,
            secret_key=security_cfg.secret_key,
            algorithm=security_cfg.algorithm,
            expected_type=TokenType.ACCESS,
        )
    except ValueError:
        raise credentials_exception

    username: str | None = payload.get("sub")
    if not username:
        raise credentials_exception

    user = db.query(User).filter(User.username == username).first()
    if not user:
        logger.warning("JWT references unknown user", username=username)
        raise credentials_exception

    if user.status == UserStatus.LOCKED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been locked. Contact an administrator.",
        )
    if user.status == UserStatus.INACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is inactive.",
        )

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


# ---------------------------------------------------------------------------
# Role guards
# ---------------------------------------------------------------------------

class RequireRoles:
    """
    Dependency class that enforces a minimum set of allowed roles.

    Usage::

        @router.post("/clusters")
        def create_cluster(
            _: Annotated[User, Depends(RequireRoles(UserRole.ADMIN, UserRole.OPS))],
        ):
            ...
    """

    def __init__(self, *roles: UserRole) -> None:
        self._roles = set(roles)

    def __call__(self, user: CurrentUser) -> User:
        if user.is_superuser:
            return user
        if user.role not in self._roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"This action requires one of these roles: "
                    f"{', '.join(r.value for r in self._roles)}"
                ),
            )
        return user


require_admin = RequireRoles(UserRole.ADMIN)
require_ops_or_admin = RequireRoles(UserRole.ADMIN, UserRole.OPS)
require_billing = RequireRoles(UserRole.ADMIN, UserRole.BILLING)
