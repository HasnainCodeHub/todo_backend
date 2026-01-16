# Authentication Dependency Module
# Phase 2.3: JWT Authentication
# Task ID: T004-T009

from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Header, HTTPException, status

from ..config import settings


@dataclass
class AuthenticatedUser:
    """
    Represents an authenticated user extracted from JWT.

    Implements FR-004: Extract user identity (user_id, email) from JWT payload.
    Task ID: T004
    """
    user_id: str
    email: str


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None
) -> AuthenticatedUser:
    """
    FastAPI dependency for JWT authentication.

    Implements:
    - FR-001: Require valid JWT token in Authorization header
    - FR-002: Validate JWT signature using shared secret
    - FR-003: Validate JWT expiration
    - FR-004: Extract user identity from JWT payload
    - FR-005: Reject missing/invalid tokens with 401
    - FR-012/FR-013: Return consistent error responses

    Task ID: T005-T009

    Args:
        authorization: Authorization header value (Bearer <token>)

    Returns:
        AuthenticatedUser with user_id and email from JWT

    Raises:
        HTTPException 401: Missing, invalid, or expired token
    """
    from ..config import settings

    # T005: Check for Authorization header
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # T005: Validate Bearer format
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]

    try:
        # T006: Verify JWT signature
        # T007: Validate expiration (handled by PyJWT)
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )

        # T008: Extract required claims
        user_id = payload.get("sub")
        email = payload.get("email")

        if not user_id or not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing required claims",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return AuthenticatedUser(user_id=user_id, email=email)

    except jwt.ExpiredSignatureError:
        # T009: Handle expired token
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        # T009: Handle invalid token
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def validate_and_extract_user(authorization: str = Header(None)) -> AuthenticatedUser:
    """
    Extract and validate user from JWT token, with enhanced security checks.

    Args:
        authorization: Authorization header containing JWT

    Returns:
        AuthenticatedUser with extracted user context

    Raises:
        HTTPException: If authentication fails
    """
    from ..config import settings

    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )

    # Parse "Bearer <token>"
    try:
        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization header format"
            )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format"
        )

    token = parts[1]

    # Decode and validate JWT with additional security checks
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )

        user_id = payload.get("sub")
        email = payload.get("email")

        if not user_id or not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing required claims"
            )

        # Additional security: verify that user_id is a string and not empty
        if not isinstance(user_id, str) or not user_id.strip():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: user_id must be a non-empty string"
            )

        # Validate email if present
        if email and not isinstance(email, str):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: email claim must be a string"
            )

        return AuthenticatedUser(user_id=user_id.strip(), email=email)

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired"
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
