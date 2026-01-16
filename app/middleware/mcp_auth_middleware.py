"""Pure ASGI middleware for MCP server authentication.

Extracts JWT from Authorization header on incoming MCP HTTP requests,
validates it, and stores the authenticated user in a contextvars.ContextVar
so MCP tool functions can access user identity without parameter passing.

NOTE: This is a pure ASGI middleware (not BaseHTTPMiddleware) so that lifespan
events are forwarded correctly to the wrapped FastMCP app, allowing the
StreamableHTTPSessionManager task group to initialize on startup.
"""

import json
import logging
from starlette.types import ASGIApp, Scope, Receive, Send

from ..dependencies.auth import validate_and_extract_user
from ..dependencies.mcp_auth_context import current_user_var

logger = logging.getLogger(__name__)


class MCPAuthMiddleware:
    """Pure ASGI middleware that validates JWT and sets user context for MCP tools.

    Unlike BaseHTTPMiddleware, this forwards lifespan and other non-HTTP events
    directly to the inner app, which is required for FastMCP's session manager
    to initialise its task group via its lifespan handler.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # Forward lifespan (and websocket) events unchanged so FastMCP can
        # initialise its StreamableHTTPSessionManager task group.
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Extract Authorization header from the raw ASGI scope headers.
        headers = {k.lower(): v for k, v in scope.get("headers", [])}
        auth_header = headers.get(b"authorization", b"").decode()

        if not auth_header:
            await self._send_json(send, 401, {"error": "Authentication required for MCP tools"})
            return

        try:
            user = validate_and_extract_user(auth_header)
        except Exception as e:
            logger.warning(f"MCP auth failed: {e}")
            await self._send_json(send, 401, {"error": f"Authentication failed: {str(e)}"})
            return

        token = current_user_var.set(user)
        logger.debug(f"MCP auth context set for user: {user.user_id}")

        try:
            await self.app(scope, receive, send)
        finally:
            current_user_var.reset(token)

    @staticmethod
    async def _send_json(send: Send, status: int, body: dict) -> None:
        """Send a minimal JSON HTTP response."""
        encoded = json.dumps(body).encode()
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [
                [b"content-type", b"application/json"],
                [b"content-length", str(len(encoded)).encode()],
            ],
        })
        await send({
            "type": "http.response.body",
            "body": encoded,
            "more_body": False,
        })
