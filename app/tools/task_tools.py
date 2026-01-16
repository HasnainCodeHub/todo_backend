"""MCP tools for task management with context-based user scoping.

Authentication is handled by MCPAuthMiddleware which extracts JWT from
HTTP headers and stores the authenticated user in a contextvars.ContextVar.
Tools access the user via get_current_mcp_user() - no authorization parameter needed.
"""

from typing import Dict, Any
from mcp.server.fastmcp import FastMCP

from ..crud.task import create_task, get_tasks, update_task, delete_task, toggle_complete, get_task_stats, bulk_update_tasks
from ..dependencies.mcp_auth_context import get_current_mcp_user

# Create FastMCP application with stateless HTTP transport
mcp_app = FastMCP(
    name="todo-mcp-server",
    stateless_http=True,
    json_response=True,
)


@mcp_app.tool(
    name="add_task",
    description="Create a new task for the current user."
)
async def add_task(title: str, description: str = "") -> Dict[str, Any]:
    """Create a new task for the authenticated user.

    Args:
        title: The title of the task
        description: Optional description of the task

    Returns:
        Dictionary containing the created task details
    """
    try:
        current_user = get_current_mcp_user()

        result = create_task(
            title=title,
            user_id=current_user.user_id,
            description=description if description else None
        )

        return {
            "success": True,
            "data": result.dict(),
            "error": None,
            "metadata": {
                "tool": "add_task",
                "timestamp": result.created_at.isoformat(),
                "user_id": current_user.user_id
            }
        }
    except ValueError as e:
        return {"success": False, "data": None, "error": str(e), "metadata": {"tool": "add_task"}}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e), "metadata": {"tool": "add_task"}}


@mcp_app.tool(
    name="list_tasks",
    description="Get all tasks for the current user."
)
async def list_tasks() -> Dict[str, Any]:
    """Retrieve all tasks for the authenticated user.

    Returns:
        Dictionary containing a list of user's tasks
    """
    try:
        current_user = get_current_mcp_user()

        tasks = get_tasks(user_id=current_user.user_id)

        return {
            "success": True,
            "data": [task.dict() for task in tasks],
            "error": None,
            "metadata": {
                "tool": "list_tasks",
                "timestamp": "current",
                "user_id": current_user.user_id,
                "count": len(tasks)
            }
        }
    except ValueError as e:
        return {"success": False, "data": None, "error": str(e), "metadata": {"tool": "list_tasks"}}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e), "metadata": {"tool": "list_tasks"}}


@mcp_app.tool(
    name="complete_task",
    description="Mark a task as completed or toggle its completion status."
)
async def complete_task(task_id: int) -> Dict[str, Any]:
    """Toggle the completion status of a task for the authenticated user.

    Args:
        task_id: The ID of the task to complete

    Returns:
        Dictionary containing the updated task details
    """
    try:
        current_user = get_current_mcp_user()

        result = toggle_complete(task_id=task_id, user_id=current_user.user_id)

        if result is None:
            return {
                "success": False,
                "data": None,
                "error": "Task not found or access denied",
                "metadata": {"tool": "complete_task", "task_id": task_id}
            }

        return {
            "success": True,
            "data": result.dict(),
            "error": None,
            "metadata": {
                "tool": "complete_task",
                "timestamp": result.updated_at.isoformat(),
                "user_id": current_user.user_id,
                "task_id": task_id
            }
        }
    except ValueError as e:
        return {"success": False, "data": None, "error": str(e), "metadata": {"tool": "complete_task"}}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e), "metadata": {"tool": "complete_task"}}


@mcp_app.tool(
    name="update_task",
    description="Update an existing task's title, description, or completion status."
)
async def update_task_mcp(
    task_id: int,
    title: str = None,
    description: str = None,
    completed: bool = None,
) -> Dict[str, Any]:
    """Update an existing task for the authenticated user.

    Args:
        task_id: The ID of the task to update
        title: New title (optional)
        description: New description (optional)
        completed: New completion status (optional)

    Returns:
        Dictionary containing the updated task details
    """
    try:
        current_user = get_current_mcp_user()

        result = update_task(
            task_id=task_id,
            user_id=current_user.user_id,
            title=title if title is not None and title != "" else None,
            description=description if description is not None else None,
            completed=completed if completed is not None else None
        )

        if result is None:
            return {
                "success": False,
                "data": None,
                "error": "Task not found or access denied",
                "metadata": {"tool": "update_task", "task_id": task_id}
            }

        return {
            "success": True,
            "data": result.dict(),
            "error": None,
            "metadata": {
                "tool": "update_task",
                "timestamp": result.updated_at.isoformat(),
                "user_id": current_user.user_id,
                "task_id": task_id
            }
        }
    except ValueError as e:
        return {"success": False, "data": None, "error": str(e), "metadata": {"tool": "update_task"}}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e), "metadata": {"tool": "update_task"}}


@mcp_app.tool(
    name="delete_task",
    description="Delete a task permanently."
)
async def delete_task_mcp(task_id: int) -> Dict[str, Any]:
    """Delete a task for the authenticated user.

    Args:
        task_id: The ID of the task to delete

    Returns:
        Dictionary confirming deletion
    """
    try:
        current_user = get_current_mcp_user()

        success = delete_task(task_id=task_id, user_id=current_user.user_id)

        if not success:
            return {
                "success": False,
                "data": None,
                "error": "Task not found or access denied",
                "metadata": {"tool": "delete_task", "task_id": task_id}
            }

        return {
            "success": True,
            "data": {"id": task_id, "deleted": True},
            "error": None,
            "metadata": {
                "tool": "delete_task",
                "timestamp": "current",
                "user_id": current_user.user_id,
                "task_id": task_id
            }
        }
    except ValueError as e:
        return {"success": False, "data": None, "error": str(e), "metadata": {"tool": "delete_task"}}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e), "metadata": {"tool": "delete_task"}}


@mcp_app.tool(
    name="get_task_stats",
    description="Get task statistics (total, completed, pending) for the current user."
)
async def get_task_stats_mcp() -> Dict[str, Any]:
    """Get task statistics for the authenticated user.

    Returns:
        Dictionary containing task statistics
    """
    try:
        current_user = get_current_mcp_user()

        stats = get_task_stats(user_id=current_user.user_id)

        return {
            "success": True,
            "data": stats,
            "error": None,
            "metadata": {
                "tool": "get_task_stats",
                "timestamp": "current",
                "user_id": current_user.user_id
            }
        }
    except ValueError as e:
        return {"success": False, "data": None, "error": str(e), "metadata": {"tool": "get_task_stats"}}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e), "metadata": {"tool": "get_task_stats"}}


@mcp_app.tool(
    name="bulk_update_tasks",
    description="Update multiple tasks at once."
)
async def bulk_update_tasks_mcp(
    task_ids: list[int],
    title: str = None,
    description: str = None,
    completed: bool = None,
) -> Dict[str, Any]:
    """Update multiple tasks for the authenticated user.

    Args:
        task_ids: List of task IDs to update
        title: New title (optional)
        description: New description (optional)
        completed: New completion status (optional)

    Returns:
        Dictionary containing the number of updated tasks
    """
    try:
        current_user = get_current_mcp_user()

        updates = {}
        if title is not None:
            updates['title'] = title
        if description is not None:
            updates['description'] = description
        if completed is not None:
            updates['completed'] = completed

        updated_count = bulk_update_tasks(
            task_ids=task_ids,
            user_id=current_user.user_id,
            **updates
        )

        return {
            "success": True,
            "data": {"updated_count": updated_count, "task_ids": task_ids},
            "error": None,
            "metadata": {
                "tool": "bulk_update_tasks",
                "timestamp": "current",
                "user_id": current_user.user_id,
                "task_ids": task_ids
            }
        }
    except ValueError as e:
        return {"success": False, "data": None, "error": str(e), "metadata": {"tool": "bulk_update_tasks"}}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e), "metadata": {"tool": "bulk_update_tasks"}}
