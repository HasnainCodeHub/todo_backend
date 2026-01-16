"""Unit tests for MCP task tools.

These tests verify the behavior of individual MCP tool functions
with mocked dependencies to isolate the tool logic.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timezone
from fastapi import HTTPException

from app.tools.task_tools import (
    add_task,
    list_tasks,
    complete_task,
    update_task_mcp,
    delete_task_mcp,
    get_task_stats_mcp,
    bulk_update_tasks_mcp,
)
from app.dependencies.auth import AuthenticatedUser
from app.models.task import Task


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_authenticated_user():
    """Create a mock authenticated user."""
    return AuthenticatedUser(user_id="test-user-123", email="test@example.com")


@pytest.fixture
def mock_task():
    """Create a mock Task object."""
    mock = MagicMock(spec=Task)
    mock.id = 1
    mock.title = "Test Task"
    mock.description = "Test Description"
    mock.user_id = "test-user-123"
    mock.completed = False
    mock.created_at = datetime.now(timezone.utc)
    mock.updated_at = datetime.now(timezone.utc)
    mock.dict.return_value = {
        "id": 1,
        "title": "Test Task",
        "description": "Test Description",
        "user_id": "test-user-123",
        "completed": False,
        "created_at": mock.created_at.isoformat(),
        "updated_at": mock.updated_at.isoformat(),
    }
    return mock


@pytest.fixture
def mock_completed_task():
    """Create a mock completed Task object."""
    mock = MagicMock(spec=Task)
    mock.id = 2
    mock.title = "Completed Task"
    mock.description = "This task is done"
    mock.user_id = "test-user-123"
    mock.completed = True
    mock.created_at = datetime.now(timezone.utc)
    mock.updated_at = datetime.now(timezone.utc)
    mock.dict.return_value = {
        "id": 2,
        "title": "Completed Task",
        "description": "This task is done",
        "user_id": "test-user-123",
        "completed": True,
        "created_at": mock.created_at.isoformat(),
        "updated_at": mock.updated_at.isoformat(),
    }
    return mock


# =============================================================================
# add_task Unit Tests
# =============================================================================

class TestAddTask:
    """Unit tests for the add_task tool."""

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.create_task')
    async def test_add_task_success(self, mock_create, mock_auth, mock_authenticated_user, mock_task):
        """Test successful task creation."""
        mock_auth.return_value = mock_authenticated_user
        mock_create.return_value = mock_task

        result = await add_task(
            title="Test Task",
            description="Test Description",
            authorization="Bearer valid-token"
        )

        assert result["success"] is True
        assert result["data"]["title"] == "Test Task"
        assert result["error"] is None
        mock_create.assert_called_once()

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.create_task')
    async def test_add_task_without_description(self, mock_create, mock_auth, mock_authenticated_user, mock_task):
        """Test task creation without description."""
        mock_auth.return_value = mock_authenticated_user
        mock_task.description = None
        mock_task.dict.return_value["description"] = None
        mock_create.return_value = mock_task

        result = await add_task(
            title="Test Task",
            authorization="Bearer valid-token"
        )

        assert result["success"] is True
        mock_create.assert_called_once()

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    async def test_add_task_auth_failure(self, mock_auth):
        """Test task creation fails without valid authentication."""
        mock_auth.side_effect = HTTPException(status_code=401, detail="Authentication required")

        result = await add_task(
            title="Test Task",
            authorization=None
        )

        assert result["success"] is False
        assert "Authentication required" in result["error"]

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.create_task')
    async def test_add_task_database_error(self, mock_create, mock_auth, mock_authenticated_user):
        """Test task creation handles database errors."""
        mock_auth.return_value = mock_authenticated_user
        mock_create.side_effect = Exception("Database connection failed")

        result = await add_task(
            title="Test Task",
            authorization="Bearer valid-token"
        )

        assert result["success"] is False
        assert "Database connection failed" in result["error"]


# =============================================================================
# list_tasks Unit Tests
# =============================================================================

class TestListTasks:
    """Unit tests for the list_tasks tool."""

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.get_tasks')
    async def test_list_tasks_success(self, mock_get_tasks, mock_auth, mock_authenticated_user, mock_task):
        """Test successful task listing."""
        mock_auth.return_value = mock_authenticated_user
        mock_get_tasks.return_value = [mock_task]

        result = await list_tasks(authorization="Bearer valid-token")

        assert result["success"] is True
        assert len(result["data"]) == 1
        assert result["metadata"]["count"] == 1

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.get_tasks')
    async def test_list_tasks_empty(self, mock_get_tasks, mock_auth, mock_authenticated_user):
        """Test listing tasks returns empty array when no tasks."""
        mock_auth.return_value = mock_authenticated_user
        mock_get_tasks.return_value = []

        result = await list_tasks(authorization="Bearer valid-token")

        assert result["success"] is True
        assert result["data"] == []
        assert result["metadata"]["count"] == 0

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.get_tasks')
    async def test_list_tasks_multiple(self, mock_get_tasks, mock_auth, mock_authenticated_user, mock_task, mock_completed_task):
        """Test listing multiple tasks."""
        mock_auth.return_value = mock_authenticated_user
        mock_get_tasks.return_value = [mock_task, mock_completed_task]

        result = await list_tasks(authorization="Bearer valid-token")

        assert result["success"] is True
        assert len(result["data"]) == 2
        assert result["metadata"]["count"] == 2

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    async def test_list_tasks_auth_failure(self, mock_auth):
        """Test list tasks fails without valid authentication."""
        mock_auth.side_effect = HTTPException(status_code=401, detail="Token expired")

        result = await list_tasks(authorization="Bearer expired-token")

        assert result["success"] is False
        assert "Token expired" in result["error"]


# =============================================================================
# complete_task Unit Tests
# =============================================================================

class TestCompleteTask:
    """Unit tests for the complete_task tool."""

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.toggle_complete')
    async def test_complete_task_success(self, mock_toggle, mock_auth, mock_authenticated_user, mock_completed_task):
        """Test successful task completion."""
        mock_auth.return_value = mock_authenticated_user
        mock_toggle.return_value = mock_completed_task

        result = await complete_task(task_id=1, authorization="Bearer valid-token")

        assert result["success"] is True
        assert result["data"]["completed"] is True

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.toggle_complete')
    async def test_complete_task_not_found(self, mock_toggle, mock_auth, mock_authenticated_user):
        """Test completing non-existent task."""
        mock_auth.return_value = mock_authenticated_user
        mock_toggle.return_value = None

        result = await complete_task(task_id=99999, authorization="Bearer valid-token")

        assert result["success"] is False
        assert "not found" in result["error"].lower() or "denied" in result["error"].lower()

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.toggle_complete')
    async def test_complete_task_idempotent(self, mock_toggle, mock_auth, mock_authenticated_user, mock_completed_task):
        """Test completing already completed task is idempotent."""
        mock_auth.return_value = mock_authenticated_user
        mock_toggle.return_value = mock_completed_task

        # First completion
        result1 = await complete_task(task_id=2, authorization="Bearer valid-token")
        assert result1["success"] is True

        # Second completion should also succeed
        result2 = await complete_task(task_id=2, authorization="Bearer valid-token")
        assert result2["success"] is True


# =============================================================================
# update_task Unit Tests
# =============================================================================

class TestUpdateTask:
    """Unit tests for the update_task tool."""

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.update_task')
    async def test_update_task_title(self, mock_update, mock_auth, mock_authenticated_user, mock_task):
        """Test updating task title."""
        mock_auth.return_value = mock_authenticated_user
        mock_task.title = "Updated Title"
        mock_task.dict.return_value["title"] = "Updated Title"
        mock_update.return_value = mock_task

        result = await update_task_mcp(
            task_id=1,
            title="Updated Title",
            authorization="Bearer valid-token"
        )

        assert result["success"] is True
        assert result["data"]["title"] == "Updated Title"

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.update_task')
    async def test_update_task_description(self, mock_update, mock_auth, mock_authenticated_user, mock_task):
        """Test updating task description."""
        mock_auth.return_value = mock_authenticated_user
        mock_task.description = "Updated Description"
        mock_task.dict.return_value["description"] = "Updated Description"
        mock_update.return_value = mock_task

        result = await update_task_mcp(
            task_id=1,
            description="Updated Description",
            authorization="Bearer valid-token"
        )

        assert result["success"] is True
        assert result["data"]["description"] == "Updated Description"

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.update_task')
    async def test_update_task_both_fields(self, mock_update, mock_auth, mock_authenticated_user, mock_task):
        """Test updating both title and description."""
        mock_auth.return_value = mock_authenticated_user
        mock_task.title = "New Title"
        mock_task.description = "New Description"
        mock_task.dict.return_value["title"] = "New Title"
        mock_task.dict.return_value["description"] = "New Description"
        mock_update.return_value = mock_task

        result = await update_task_mcp(
            task_id=1,
            title="New Title",
            description="New Description",
            authorization="Bearer valid-token"
        )

        assert result["success"] is True
        assert result["data"]["title"] == "New Title"
        assert result["data"]["description"] == "New Description"

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.update_task')
    async def test_update_task_not_found(self, mock_update, mock_auth, mock_authenticated_user):
        """Test updating non-existent task."""
        mock_auth.return_value = mock_authenticated_user
        mock_update.return_value = None

        result = await update_task_mcp(
            task_id=99999,
            title="Should Fail",
            authorization="Bearer valid-token"
        )

        assert result["success"] is False
        assert "not found" in result["error"].lower() or "denied" in result["error"].lower()


# =============================================================================
# delete_task Unit Tests
# =============================================================================

class TestDeleteTask:
    """Unit tests for the delete_task tool."""

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.delete_task')
    async def test_delete_task_success(self, mock_delete, mock_auth, mock_authenticated_user):
        """Test successful task deletion."""
        mock_auth.return_value = mock_authenticated_user
        mock_delete.return_value = True

        result = await delete_task_mcp(task_id=1, authorization="Bearer valid-token")

        assert result["success"] is True
        assert result["data"]["deleted"] is True
        assert result["data"]["id"] == 1

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.delete_task')
    async def test_delete_task_not_found(self, mock_delete, mock_auth, mock_authenticated_user):
        """Test deleting non-existent task."""
        mock_auth.return_value = mock_authenticated_user
        mock_delete.return_value = False

        result = await delete_task_mcp(task_id=99999, authorization="Bearer valid-token")

        assert result["success"] is False
        assert "not found" in result["error"].lower() or "denied" in result["error"].lower()

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    async def test_delete_task_auth_failure(self, mock_auth):
        """Test delete task fails without valid authentication."""
        mock_auth.side_effect = HTTPException(status_code=401, detail="Invalid token")

        result = await delete_task_mcp(task_id=1, authorization="Bearer invalid-token")

        assert result["success"] is False
        assert "Invalid token" in result["error"]


# =============================================================================
# get_task_stats Unit Tests
# =============================================================================

class TestGetTaskStats:
    """Unit tests for the get_task_stats tool."""

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.get_task_stats')
    async def test_get_task_stats_success(self, mock_stats, mock_auth, mock_authenticated_user):
        """Test successful stats retrieval."""
        mock_auth.return_value = mock_authenticated_user
        mock_stats.return_value = {
            "total": 10,
            "completed": 7,
            "pending": 3,
            "completion_rate": 70.0
        }

        result = await get_task_stats_mcp(authorization="Bearer valid-token")

        assert result["success"] is True
        assert result["data"]["total"] == 10
        assert result["data"]["completed"] == 7
        assert result["data"]["pending"] == 3

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.get_task_stats')
    async def test_get_task_stats_empty(self, mock_stats, mock_auth, mock_authenticated_user):
        """Test stats with no tasks."""
        mock_auth.return_value = mock_authenticated_user
        mock_stats.return_value = {
            "total": 0,
            "completed": 0,
            "pending": 0,
            "completion_rate": 0
        }

        result = await get_task_stats_mcp(authorization="Bearer valid-token")

        assert result["success"] is True
        assert result["data"]["total"] == 0


# =============================================================================
# bulk_update_tasks Unit Tests
# =============================================================================

class TestBulkUpdateTasks:
    """Unit tests for the bulk_update_tasks tool."""

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.bulk_update_tasks')
    async def test_bulk_update_success(self, mock_bulk_update, mock_auth, mock_authenticated_user):
        """Test successful bulk update."""
        mock_auth.return_value = mock_authenticated_user
        mock_bulk_update.return_value = 3

        result = await bulk_update_tasks_mcp(
            task_ids=[1, 2, 3],
            completed=True,
            authorization="Bearer valid-token"
        )

        assert result["success"] is True
        assert result["data"]["updated_count"] == 3

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.bulk_update_tasks')
    async def test_bulk_update_no_tasks(self, mock_bulk_update, mock_auth, mock_authenticated_user):
        """Test bulk update with no matching tasks."""
        mock_auth.return_value = mock_authenticated_user
        mock_bulk_update.return_value = 0

        result = await bulk_update_tasks_mcp(
            task_ids=[999, 998, 997],
            completed=True,
            authorization="Bearer valid-token"
        )

        assert result["success"] is True
        assert result["data"]["updated_count"] == 0


# =============================================================================
# Response Format Tests
# =============================================================================

class TestResponseFormats:
    """Tests to verify consistent response formats."""

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.create_task')
    async def test_success_response_has_all_fields(self, mock_create, mock_auth, mock_authenticated_user, mock_task):
        """Verify success response contains all required fields."""
        mock_auth.return_value = mock_authenticated_user
        mock_create.return_value = mock_task

        result = await add_task(title="Test", authorization="Bearer valid-token")

        assert "success" in result
        assert "data" in result
        assert "error" in result
        assert "metadata" in result

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    async def test_error_response_has_all_fields(self, mock_auth):
        """Verify error response contains all required fields."""
        mock_auth.side_effect = HTTPException(status_code=401, detail="Auth failed")

        result = await add_task(title="Test", authorization=None)

        assert "success" in result
        assert "data" in result
        assert "error" in result
        assert "metadata" in result
        assert result["success"] is False
        assert result["data"] is None
