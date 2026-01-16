"""MCP Tools package for task management.

This package contains the MCP tool definitions for AI agent interactions.
"""

from .task_tools import (
    mcp_app,
    add_task,
    list_tasks,
    complete_task,
    update_task_mcp,
    delete_task_mcp,
    get_task_stats_mcp,
    bulk_update_tasks_mcp,
)

__all__ = [
    "mcp_app",
    "add_task",
    "list_tasks",
    "complete_task",
    "update_task_mcp",
    "delete_task_mcp",
    "get_task_stats_mcp",
    "bulk_update_tasks_mcp",
]
