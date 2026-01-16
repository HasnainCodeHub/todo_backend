"""Context-based authentication for MCP tool calls.

Uses Python's contextvars to bridge HTTP-layer JWT authentication
into MCP tool function scope without passing auth as tool parameters.
"""

import contextvars
import logging
from typing import Optional

from .auth import AuthenticatedUser

logger = logging.getLogger(__name__)

# Context variable holding the authenticated user for the current MCP request
current_user_var: contextvars.ContextVar[Optional[AuthenticatedUser]] = contextvars.ContextVar(
    'current_user', default=None
)


def get_current_mcp_user() -> AuthenticatedUser:
    """Get the authenticated user from the current MCP request context.

    Returns:
        AuthenticatedUser extracted from JWT by the MCPAuthMiddleware.

    Raises:
        ValueError: If no authenticated user is in context.
    """
    user = current_user_var.get()
    if user is None:
        raise ValueError("No authenticated user in MCP context. Ensure MCPAuthMiddleware is applied.")
    return user
