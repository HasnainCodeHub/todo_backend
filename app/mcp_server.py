"""MCP Server implementation for AI Task Management.

This module provides the MCP (Model Context Protocol) server setup using FastMCP.
It exposes task management tools for AI agents to interact with the todo system.
"""

import logging
from typing import Dict, Any

from mcp.server.fastmcp import FastMCP

from .tools.task_tools import mcp_app

logger = logging.getLogger(__name__)


def get_mcp_app():
    """
    Get the MCP application instance configured for HTTP streaming.

    Returns:
        The FastMCP application configured for streamable HTTP transport.
    """
    logger.info("Initializing MCP server for task management")

    # The mcp_app is already configured in task_tools.py with:
    # - stateless_http=True for stateless operation
    # - json_response=True for JSON responses
    # - All task management tools registered

    # Return the streamable HTTP app for mounting
    return mcp_app.streamable_http_app()


def get_mcp_server():
    """
    Get the raw MCP server instance for direct use.

    Returns:
        The FastMCP server instance.
    """
    return mcp_app


# Tool registration verification
def verify_tools():
    """
    Verify that all expected tools are registered.

    Returns:
        Dictionary with tool verification results.
    """
    expected_tools = [
        "add_task",
        "list_tasks",
        "complete_task",
        "update_task",
        "delete_task",
        "get_task_stats",
        "bulk_update_tasks"
    ]

    # Get registered tools from mcp_app
    registered_tools = list(mcp_app._tool_manager._tools.keys()) if hasattr(mcp_app, '_tool_manager') else []

    missing_tools = [tool for tool in expected_tools if tool not in registered_tools]
    extra_tools = [tool for tool in registered_tools if tool not in expected_tools]

    return {
        "registered_tools": registered_tools,
        "expected_tools": expected_tools,
        "missing_tools": missing_tools,
        "extra_tools": extra_tools,
        "all_registered": len(missing_tools) == 0
    }


if __name__ == "__main__":
    # When run directly, verify tools and print status
    verification = verify_tools()
    print("MCP Server Tool Verification:")
    print(f"  Registered: {verification['registered_tools']}")
    print(f"  Missing: {verification['missing_tools']}")
    print(f"  All registered: {verification['all_registered']}")
