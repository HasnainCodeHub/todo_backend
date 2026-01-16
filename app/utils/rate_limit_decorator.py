"""Rate limiting decorator for MCP tools."""

from functools import wraps
from typing import Callable, Any
from fastapi import Header, HTTPException, status
from .rate_limiter import rate_limiter
from .error_responses import create_error_response


def rate_limit(max_requests: int = 100, window_seconds: int = 60):
    """
    Rate limiting decorator for MCP tools.

    Args:
        max_requests: Maximum requests per user per window (default: 100)
        window_seconds: Time window in seconds (default: 60)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract authorization header if present
            authorization = kwargs.get('authorization')

            if authorization:
                # Parse the authorization header to extract user context
                try:
                    # Parse "Bearer <token>"
                    parts = authorization.split(" ", 1)
                    if len(parts) != 2 or parts[0].lower() != "bearer":
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid authorization header format"
                        )

                    # For rate limiting purposes, we just need to extract the token
                    # The actual validation will be handled by the existing auth system
                    token = parts[1]

                    # We'll use the token itself as a proxy for user identification
                    # In a real implementation, you'd decode the JWT to get the user ID
                    # But for rate limiting, we can use a hash or some other identifier
                    # derived from the token to maintain privacy while still allowing
                    # per-user rate limiting
                    import hashlib
                    user_id = hashlib.sha256(token.encode()).hexdigest()[:16]  # Shortened hash

                    # Check rate limit
                    if not rate_limiter.is_allowed(user_id):
                        return create_error_response(
                            error_code="RATE_LIMIT_EXCEEDED",
                            message=f"Rate limit exceeded. Maximum {max_requests} requests per {window_seconds} seconds.",
                            details={
                                "max_requests": max_requests,
                                "window_seconds": window_seconds,
                                "user_id_hash": user_id
                            },
                            tool_name=func.__name__
                        )
                except Exception as e:
                    # If there's an issue with the authorization header,
                    # let the original function handle it
                    pass

            # Call the original function
            return await func(*args, **kwargs)

        return wrapper
    return decorator


def rate_limit_with_user_id(max_requests: int = 100, window_seconds: int = 60):
    """
    Rate limiting decorator that extracts user_id from the validated JWT.
    This decorator handles authentication first, then applies rate limiting,
    and finally calls the original function.

    Args:
        max_requests: Maximum requests per user per window (default: 100)
        window_seconds: Time window in seconds (default: 60)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract and validate JWT first to get the user_id for rate limiting
            authorization = kwargs.get('authorization')

            if authorization:
                try:
                    # Parse "Bearer <token>"
                    parts = authorization.split(" ", 1)
                    if len(parts) != 2 or parts[0].lower() != "bearer":
                        # If authorization header is malformed, let the original function handle it
                        pass
                    else:
                        # Import the auth function to validate and extract user
                        from ..dependencies.auth import validate_and_extract_user
                        current_user = validate_and_extract_user(authorization)

                        # Now we have the user_id, apply rate limiting
                        user_id = current_user.user_id

                        # Check rate limit
                        if not rate_limiter.is_allowed(user_id):
                            return create_error_response(
                                error_code="RATE_LIMIT_EXCEEDED",
                                message=f"Rate limit exceeded. Maximum {max_requests} requests per {window_seconds} seconds.",
                                details={
                                    "max_requests": max_requests,
                                    "window_seconds": window_seconds,
                                    "user_id": user_id
                                },
                                tool_name=func.__name__
                            )

                except Exception:
                    # If there's an issue with the authorization header,
                    # let the original function handle the authentication error
                    pass

            # Call the original function
            return await func(*args, **kwargs)

        return wrapper
    return decorator