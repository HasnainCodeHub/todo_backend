"""
Contract tests for MCP Task Tools.

These tests verify that each MCP tool adheres to the contracts defined in:
specs/008-mcp-server/contracts/mcp-task-tools.yaml

The contracts specify:
1. Input validation (required fields, type checking, length limits)
2. Output schema compliance (success response format, error response format)
3. Authentication requirements (JWT in Authorization header)
4. User scoping (tasks belong to specific users)

Tools tested:
- add_task: Create a new task
- list_tasks: Retrieve tasks with optional status filter
- complete_task: Mark a task as completed
- delete_task: Remove a task
- update_task: Modify task title and/or description
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timedelta, timezone
from typing import Dict, Any
import jwt

# Import the tools module to test
from app.tools.task_tools import (
    add_task,
    list_tasks,
    complete_task,
    update_task_mcp,
    delete_task_mcp,
)
from app.dependencies.auth import AuthenticatedUser
from app.models.task import Task


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def jwt_secret():
    """JWT secret for testing."""
    return "test-jwt-secret-for-contract-tests"


@pytest.fixture
def valid_user_id():
    """Valid user ID for testing."""
    return "test-user-123"


@pytest.fixture
def valid_token(jwt_secret, valid_user_id):
    """Generate a valid JWT token for testing."""
    payload = {
        "sub": valid_user_id,
        "email": "test@example.com",
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return jwt.encode(payload, jwt_secret, algorithm="HS256")


@pytest.fixture
def valid_authorization(valid_token):
    """Valid Authorization header value."""
    return f"Bearer {valid_token}"


@pytest.fixture
def expired_token(jwt_secret, valid_user_id):
    """Generate an expired JWT token for testing."""
    payload = {
        "sub": valid_user_id,
        "email": "test@example.com",
        "iat": datetime.now(timezone.utc) - timedelta(hours=2),
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
    }
    return jwt.encode(payload, jwt_secret, algorithm="HS256")


@pytest.fixture
def mock_authenticated_user(valid_user_id):
    """Create a mock AuthenticatedUser."""
    return AuthenticatedUser(user_id=valid_user_id, email="test@example.com")


@pytest.fixture
def mock_task(valid_user_id):
    """Create a mock Task object."""
    mock = MagicMock(spec=Task)
    mock.id = 1
    mock.title = "Test Task"
    mock.description = "Test Description"
    mock.user_id = valid_user_id
    mock.completed = False
    mock.created_at = datetime.now(timezone.utc)
    mock.updated_at = datetime.now(timezone.utc)
    mock.dict.return_value = {
        "id": 1,
        "title": "Test Task",
        "description": "Test Description",
        "user_id": valid_user_id,
        "completed": False,
        "created_at": mock.created_at.isoformat(),
        "updated_at": mock.updated_at.isoformat(),
    }
    return mock


@pytest.fixture
def completed_task(valid_user_id):
    """Create a mock completed Task object."""
    mock = MagicMock(spec=Task)
    mock.id = 2
    mock.title = "Completed Task"
    mock.description = "This task is completed"
    mock.user_id = valid_user_id
    mock.completed = True
    mock.created_at = datetime.now(timezone.utc)
    mock.updated_at = datetime.now(timezone.utc)
    mock.dict.return_value = {
        "id": 2,
        "title": "Completed Task",
        "description": "This task is completed",
        "user_id": valid_user_id,
        "completed": True,
        "created_at": mock.created_at.isoformat(),
        "updated_at": mock.updated_at.isoformat(),
    }
    return mock


# =============================================================================
# Helper Functions for Contract Validation
# =============================================================================

def validate_success_response_structure(response: Dict[str, Any]) -> None:
    """
    Validate that a success response matches the contract structure:
    {
        "success": True,
        "data": ...,
        "error": None,
        "metadata": {"tool": str, "timestamp": str, "user_id": str}
    }
    """
    assert "success" in response, "Response must contain 'success' field"
    assert "data" in response, "Response must contain 'data' field"
    assert "error" in response, "Response must contain 'error' field"
    assert "metadata" in response, "Response must contain 'metadata' field"

    assert response["success"] is True, "Success response must have success=True"
    assert response["error"] is None, "Success response must have error=None"

    metadata = response["metadata"]
    assert "tool" in metadata, "Metadata must contain 'tool' field"
    assert "timestamp" in metadata, "Metadata must contain 'timestamp' field"
    assert "user_id" in metadata, "Metadata must contain 'user_id' field"


def validate_error_response_structure(response: Dict[str, Any]) -> None:
    """
    Validate that an error response matches the contract structure:
    {
        "success": False,
        "data": None,
        "error": str,
        "metadata": {"tool": str, "timestamp": str, "user_id": str}
    }
    """
    assert "success" in response, "Response must contain 'success' field"
    assert "data" in response, "Response must contain 'data' field"
    assert "error" in response, "Response must contain 'error' field"
    assert "metadata" in response, "Response must contain 'metadata' field"

    assert response["success"] is False, "Error response must have success=False"
    assert response["data"] is None, "Error response must have data=None"
    assert response["error"] is not None, "Error response must have non-None error"
    assert isinstance(response["error"], str), "Error must be a string"


def validate_task_object(task: Dict[str, Any]) -> None:
    """
    Validate that a task object matches the contract schema:
    {
        "id": int,
        "user_id": str,
        "title": str,
        "description": str | None,
        "completed": bool,
        "created_at": str (datetime),
        "updated_at": str (datetime)
    }
    """
    required_fields = ["id", "user_id", "title", "completed", "created_at", "updated_at"]
    for field in required_fields:
        assert field in task, f"Task must contain '{field}' field"

    assert isinstance(task["id"], int), "Task id must be an integer"
    assert isinstance(task["user_id"], str), "Task user_id must be a string"
    assert isinstance(task["title"], str), "Task title must be a string"
    assert isinstance(task["completed"], bool), "Task completed must be a boolean"

    # description is optional but if present must be string or None
    if "description" in task and task["description"] is not None:
        assert isinstance(task["description"], str), "Task description must be a string or None"


# =============================================================================
# add_task Contract Tests
# =============================================================================

class TestAddTaskContract:
    """Contract tests for the add_task MCP tool."""

    # -------------------------------------------------------------------------
    # Input Validation Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.create_task')
    async def test_add_task_requires_title(
        self, mock_create_task, mock_auth, mock_authenticated_user, valid_authorization
    ):
        """Contract: title is a required field (must be non-empty string)."""
        mock_auth.return_value = mock_authenticated_user
        mock_create_task.side_effect = ValueError("Title is required")

        # Empty title should result in error
        result = await add_task(title="", description="Test", authorization=valid_authorization)

        validate_error_response_structure(result)
        assert "metadata" in result
        assert result["metadata"]["tool"] == "add_task"

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.create_task')
    async def test_add_task_title_max_length(
        self, mock_create_task, mock_auth, mock_authenticated_user, mock_task, valid_authorization
    ):
        """Contract: title maxLength is 200 characters."""
        mock_auth.return_value = mock_authenticated_user
        mock_create_task.return_value = mock_task

        # Title exactly at limit should succeed
        title_at_limit = "a" * 200
        mock_task.title = title_at_limit
        mock_task.dict.return_value["title"] = title_at_limit

        result = await add_task(title=title_at_limit, authorization=valid_authorization)

        validate_success_response_structure(result)
        mock_create_task.assert_called_once()

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.create_task')
    async def test_add_task_description_optional(
        self, mock_create_task, mock_auth, mock_authenticated_user, mock_task, valid_authorization
    ):
        """Contract: description is optional (can be omitted or empty)."""
        mock_auth.return_value = mock_authenticated_user
        mock_task.description = None
        mock_task.dict.return_value["description"] = None
        mock_create_task.return_value = mock_task

        # No description provided
        result = await add_task(title="Test Task", authorization=valid_authorization)

        validate_success_response_structure(result)
        mock_create_task.assert_called_once()

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.create_task')
    async def test_add_task_description_max_length(
        self, mock_create_task, mock_auth, mock_authenticated_user, mock_task, valid_authorization
    ):
        """Contract: description maxLength is 1000 characters."""
        mock_auth.return_value = mock_authenticated_user
        mock_create_task.return_value = mock_task

        # Description exactly at limit should succeed
        desc_at_limit = "b" * 1000
        mock_task.description = desc_at_limit
        mock_task.dict.return_value["description"] = desc_at_limit

        result = await add_task(
            title="Test Task",
            description=desc_at_limit,
            authorization=valid_authorization
        )

        validate_success_response_structure(result)

    # -------------------------------------------------------------------------
    # Output Schema Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.create_task')
    async def test_add_task_success_response_schema(
        self, mock_create_task, mock_auth, mock_authenticated_user, mock_task, valid_authorization
    ):
        """Contract: Success response contains success=true and task object."""
        mock_auth.return_value = mock_authenticated_user
        mock_create_task.return_value = mock_task

        result = await add_task(
            title="Test Task",
            description="Test Description",
            authorization=valid_authorization
        )

        validate_success_response_structure(result)
        assert result["data"] is not None
        validate_task_object(result["data"])
        assert result["metadata"]["tool"] == "add_task"

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.create_task')
    async def test_add_task_new_task_defaults(
        self, mock_create_task, mock_auth, mock_authenticated_user, mock_task, valid_authorization
    ):
        """Contract: Newly created task has completed=false by default."""
        mock_auth.return_value = mock_authenticated_user
        mock_create_task.return_value = mock_task

        result = await add_task(title="New Task", authorization=valid_authorization)

        validate_success_response_structure(result)
        assert result["data"]["completed"] is False

    # -------------------------------------------------------------------------
    # Authentication Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    async def test_add_task_requires_authorization(self, mock_auth):
        """Contract: Tool requires valid JWT in Authorization header."""
        from fastapi import HTTPException
        mock_auth.side_effect = HTTPException(status_code=401, detail="Authentication required")

        result = await add_task(title="Test Task", authorization=None)

        validate_error_response_structure(result)
        assert "Authentication required" in result["error"]

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    async def test_add_task_rejects_invalid_token(self, mock_auth):
        """Contract: Invalid JWT results in authentication error."""
        from fastapi import HTTPException
        mock_auth.side_effect = HTTPException(status_code=401, detail="Invalid token")

        result = await add_task(title="Test Task", authorization="Bearer invalid-token")

        validate_error_response_structure(result)

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    async def test_add_task_rejects_expired_token(self, mock_auth, expired_token):
        """Contract: Expired JWT results in authentication error."""
        from fastapi import HTTPException
        mock_auth.side_effect = HTTPException(status_code=401, detail="Token expired")

        result = await add_task(title="Test Task", authorization=f"Bearer {expired_token}")

        validate_error_response_structure(result)

    # -------------------------------------------------------------------------
    # User Scoping Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.create_task')
    async def test_add_task_creates_for_authenticated_user(
        self, mock_create_task, mock_auth, mock_authenticated_user, mock_task, valid_authorization
    ):
        """Contract: Task is created for the authenticated user only."""
        mock_auth.return_value = mock_authenticated_user
        mock_create_task.return_value = mock_task

        result = await add_task(title="Test Task", authorization=valid_authorization)

        # Verify create_task was called with the authenticated user's ID
        mock_create_task.assert_called_once()
        call_kwargs = mock_create_task.call_args
        assert call_kwargs.kwargs["user_id"] == mock_authenticated_user.user_id


# =============================================================================
# list_tasks Contract Tests
# =============================================================================

class TestListTasksContract:
    """Contract tests for the list_tasks MCP tool."""

    # -------------------------------------------------------------------------
    # Input Validation Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.get_tasks')
    async def test_list_tasks_status_default_all(
        self, mock_get_tasks, mock_auth, mock_authenticated_user, valid_authorization
    ):
        """Contract: status defaults to 'all' when not provided."""
        mock_auth.return_value = mock_authenticated_user
        mock_get_tasks.return_value = []

        result = await list_tasks(authorization=valid_authorization)

        validate_success_response_structure(result)
        # Default is to get all tasks (no status filter)
        mock_get_tasks.assert_called_once()

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.get_tasks')
    async def test_list_tasks_no_required_inputs(
        self, mock_get_tasks, mock_auth, mock_authenticated_user, valid_authorization
    ):
        """Contract: Only authorization is required; status is optional."""
        mock_auth.return_value = mock_authenticated_user
        mock_get_tasks.return_value = []

        result = await list_tasks(authorization=valid_authorization)

        validate_success_response_structure(result)

    # -------------------------------------------------------------------------
    # Output Schema Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.get_tasks')
    async def test_list_tasks_success_response_schema(
        self, mock_get_tasks, mock_auth, mock_authenticated_user, mock_task, valid_authorization
    ):
        """Contract: Success response contains success=true and tasks array."""
        mock_auth.return_value = mock_authenticated_user
        mock_get_tasks.return_value = [mock_task]

        result = await list_tasks(authorization=valid_authorization)

        validate_success_response_structure(result)
        assert isinstance(result["data"], list)
        assert result["metadata"]["tool"] == "list_tasks"
        assert "count" in result["metadata"]

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.get_tasks')
    async def test_list_tasks_empty_array_valid(
        self, mock_get_tasks, mock_auth, mock_authenticated_user, valid_authorization
    ):
        """Contract: Empty tasks array is a valid response."""
        mock_auth.return_value = mock_authenticated_user
        mock_get_tasks.return_value = []

        result = await list_tasks(authorization=valid_authorization)

        validate_success_response_structure(result)
        assert result["data"] == []
        assert result["metadata"]["count"] == 0

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.get_tasks')
    async def test_list_tasks_each_task_matches_schema(
        self, mock_get_tasks, mock_auth, mock_authenticated_user, mock_task, completed_task, valid_authorization
    ):
        """Contract: Each task in the array matches the task schema."""
        mock_auth.return_value = mock_authenticated_user
        mock_get_tasks.return_value = [mock_task, completed_task]

        result = await list_tasks(authorization=valid_authorization)

        validate_success_response_structure(result)
        for task in result["data"]:
            validate_task_object(task)

    # -------------------------------------------------------------------------
    # Authentication Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    async def test_list_tasks_requires_authorization(self, mock_auth):
        """Contract: Tool requires valid JWT in Authorization header."""
        from fastapi import HTTPException
        mock_auth.side_effect = HTTPException(status_code=401, detail="Authentication required")

        result = await list_tasks(authorization=None)

        validate_error_response_structure(result)

    # -------------------------------------------------------------------------
    # User Scoping Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.get_tasks')
    async def test_list_tasks_returns_only_user_tasks(
        self, mock_get_tasks, mock_auth, mock_authenticated_user, valid_authorization
    ):
        """Contract: Only returns tasks belonging to the authenticated user."""
        mock_auth.return_value = mock_authenticated_user
        mock_get_tasks.return_value = []

        result = await list_tasks(authorization=valid_authorization)

        mock_get_tasks.assert_called_once()
        call_kwargs = mock_get_tasks.call_args
        assert call_kwargs.kwargs["user_id"] == mock_authenticated_user.user_id


# =============================================================================
# complete_task Contract Tests
# =============================================================================

class TestCompleteTaskContract:
    """Contract tests for the complete_task MCP tool."""

    # -------------------------------------------------------------------------
    # Input Validation Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.toggle_complete')
    async def test_complete_task_requires_task_id(
        self, mock_toggle, mock_auth, mock_authenticated_user, valid_authorization
    ):
        """Contract: task_id is a required integer field."""
        mock_auth.return_value = mock_authenticated_user
        mock_toggle.return_value = None

        # Note: The tool signature requires task_id, so calling without it would fail at Python level
        # Here we test with an invalid task_id (non-existent)
        result = await complete_task(task_id=99999, authorization=valid_authorization)

        validate_error_response_structure(result)
        assert result["metadata"]["task_id"] == 99999

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.toggle_complete')
    async def test_complete_task_task_id_must_be_integer(
        self, mock_toggle, mock_auth, mock_authenticated_user, completed_task, valid_authorization
    ):
        """Contract: task_id type must be integer."""
        mock_auth.return_value = mock_authenticated_user
        mock_toggle.return_value = completed_task

        # Valid integer task_id
        result = await complete_task(task_id=1, authorization=valid_authorization)

        validate_success_response_structure(result)

    # -------------------------------------------------------------------------
    # Output Schema Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.toggle_complete')
    async def test_complete_task_success_response_schema(
        self, mock_toggle, mock_auth, mock_authenticated_user, completed_task, valid_authorization
    ):
        """Contract: Success response contains success=true and task with completed=true."""
        mock_auth.return_value = mock_authenticated_user
        mock_toggle.return_value = completed_task

        result = await complete_task(task_id=1, authorization=valid_authorization)

        validate_success_response_structure(result)
        assert result["data"]["completed"] is True
        assert result["metadata"]["tool"] == "complete_task"
        assert result["metadata"]["task_id"] == 1

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.toggle_complete')
    async def test_complete_task_not_found_error(
        self, mock_toggle, mock_auth, mock_authenticated_user, valid_authorization
    ):
        """Contract: Non-existent task returns error with appropriate message."""
        mock_auth.return_value = mock_authenticated_user
        mock_toggle.return_value = None  # Indicates task not found

        result = await complete_task(task_id=99999, authorization=valid_authorization)

        validate_error_response_structure(result)
        assert "not found" in result["error"].lower() or "denied" in result["error"].lower()

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.toggle_complete')
    async def test_complete_task_idempotent(
        self, mock_toggle, mock_auth, mock_authenticated_user, completed_task, valid_authorization
    ):
        """Contract: Completing an already completed task is idempotent."""
        mock_auth.return_value = mock_authenticated_user
        mock_toggle.return_value = completed_task  # Already completed

        result = await complete_task(task_id=2, authorization=valid_authorization)

        # Should succeed even if already completed
        validate_success_response_structure(result)

    # -------------------------------------------------------------------------
    # Authentication Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    async def test_complete_task_requires_authorization(self, mock_auth):
        """Contract: Tool requires valid JWT in Authorization header."""
        from fastapi import HTTPException
        mock_auth.side_effect = HTTPException(status_code=401, detail="Authentication required")

        result = await complete_task(task_id=1, authorization=None)

        validate_error_response_structure(result)

    # -------------------------------------------------------------------------
    # User Scoping Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.toggle_complete')
    async def test_complete_task_user_scoped(
        self, mock_toggle, mock_auth, mock_authenticated_user, valid_authorization
    ):
        """Contract: Can only complete tasks belonging to authenticated user."""
        mock_auth.return_value = mock_authenticated_user
        mock_toggle.return_value = None  # Simulates task not accessible

        result = await complete_task(task_id=1, authorization=valid_authorization)

        mock_toggle.assert_called_once()
        call_kwargs = mock_toggle.call_args
        assert call_kwargs.kwargs["user_id"] == mock_authenticated_user.user_id


# =============================================================================
# delete_task Contract Tests
# =============================================================================

class TestDeleteTaskContract:
    """Contract tests for the delete_task MCP tool."""

    # -------------------------------------------------------------------------
    # Input Validation Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.delete_task')
    async def test_delete_task_requires_task_id(
        self, mock_delete, mock_auth, mock_authenticated_user, valid_authorization
    ):
        """Contract: task_id is a required integer field."""
        mock_auth.return_value = mock_authenticated_user
        mock_delete.return_value = False  # Not found

        result = await delete_task_mcp(task_id=99999, authorization=valid_authorization)

        validate_error_response_structure(result)
        assert result["metadata"]["task_id"] == 99999

    # -------------------------------------------------------------------------
    # Output Schema Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.delete_task')
    async def test_delete_task_success_response_schema(
        self, mock_delete, mock_auth, mock_authenticated_user, valid_authorization
    ):
        """Contract: Success response contains success=true and deleted_task_id."""
        mock_auth.return_value = mock_authenticated_user
        mock_delete.return_value = True

        result = await delete_task_mcp(task_id=1, authorization=valid_authorization)

        validate_success_response_structure(result)
        assert result["data"]["id"] == 1
        assert result["data"]["deleted"] is True
        assert result["metadata"]["tool"] == "delete_task"

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.delete_task')
    async def test_delete_task_not_found_error(
        self, mock_delete, mock_auth, mock_authenticated_user, valid_authorization
    ):
        """Contract: Non-existent task returns error."""
        mock_auth.return_value = mock_authenticated_user
        mock_delete.return_value = False

        result = await delete_task_mcp(task_id=99999, authorization=valid_authorization)

        validate_error_response_structure(result)
        assert "not found" in result["error"].lower() or "denied" in result["error"].lower()

    # -------------------------------------------------------------------------
    # Authentication Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    async def test_delete_task_requires_authorization(self, mock_auth):
        """Contract: Tool requires valid JWT in Authorization header."""
        from fastapi import HTTPException
        mock_auth.side_effect = HTTPException(status_code=401, detail="Authentication required")

        result = await delete_task_mcp(task_id=1, authorization=None)

        validate_error_response_structure(result)

    # -------------------------------------------------------------------------
    # User Scoping Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.delete_task')
    async def test_delete_task_user_scoped(
        self, mock_delete, mock_auth, mock_authenticated_user, valid_authorization
    ):
        """Contract: Can only delete tasks belonging to authenticated user."""
        mock_auth.return_value = mock_authenticated_user
        mock_delete.return_value = True

        result = await delete_task_mcp(task_id=1, authorization=valid_authorization)

        mock_delete.assert_called_once()
        call_kwargs = mock_delete.call_args
        assert call_kwargs.kwargs["user_id"] == mock_authenticated_user.user_id


# =============================================================================
# update_task Contract Tests
# =============================================================================

class TestUpdateTaskContract:
    """Contract tests for the update_task MCP tool."""

    # -------------------------------------------------------------------------
    # Input Validation Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.update_task')
    async def test_update_task_requires_task_id(
        self, mock_update, mock_auth, mock_authenticated_user, valid_authorization
    ):
        """Contract: task_id is a required integer field."""
        mock_auth.return_value = mock_authenticated_user
        mock_update.return_value = None

        result = await update_task_mcp(task_id=99999, authorization=valid_authorization)

        validate_error_response_structure(result)
        assert result["metadata"]["task_id"] == 99999

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.update_task')
    async def test_update_task_title_optional(
        self, mock_update, mock_auth, mock_authenticated_user, mock_task, valid_authorization
    ):
        """Contract: title is optional for update."""
        mock_auth.return_value = mock_authenticated_user
        mock_update.return_value = mock_task

        # Update with only description, no title
        result = await update_task_mcp(
            task_id=1,
            description="New description only",
            authorization=valid_authorization
        )

        validate_success_response_structure(result)

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.update_task')
    async def test_update_task_title_max_length(
        self, mock_update, mock_auth, mock_authenticated_user, mock_task, valid_authorization
    ):
        """Contract: title maxLength is 200 characters."""
        mock_auth.return_value = mock_authenticated_user
        title_at_limit = "x" * 200
        mock_task.title = title_at_limit
        mock_task.dict.return_value["title"] = title_at_limit
        mock_update.return_value = mock_task

        result = await update_task_mcp(
            task_id=1,
            title=title_at_limit,
            authorization=valid_authorization
        )

        validate_success_response_structure(result)

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.update_task')
    async def test_update_task_description_optional(
        self, mock_update, mock_auth, mock_authenticated_user, mock_task, valid_authorization
    ):
        """Contract: description is optional for update."""
        mock_auth.return_value = mock_authenticated_user
        mock_update.return_value = mock_task

        # Update with only title, no description
        result = await update_task_mcp(
            task_id=1,
            title="New title only",
            authorization=valid_authorization
        )

        validate_success_response_structure(result)

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.update_task')
    async def test_update_task_description_max_length(
        self, mock_update, mock_auth, mock_authenticated_user, mock_task, valid_authorization
    ):
        """Contract: description maxLength is 1000 characters."""
        mock_auth.return_value = mock_authenticated_user
        desc_at_limit = "y" * 1000
        mock_task.description = desc_at_limit
        mock_task.dict.return_value["description"] = desc_at_limit
        mock_update.return_value = mock_task

        result = await update_task_mcp(
            task_id=1,
            description=desc_at_limit,
            authorization=valid_authorization
        )

        validate_success_response_structure(result)

    # -------------------------------------------------------------------------
    # Output Schema Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.update_task')
    async def test_update_task_success_response_schema(
        self, mock_update, mock_auth, mock_authenticated_user, mock_task, valid_authorization
    ):
        """Contract: Success response contains success=true and updated task object."""
        mock_auth.return_value = mock_authenticated_user
        mock_task.title = "Updated Title"
        mock_task.dict.return_value["title"] = "Updated Title"
        mock_update.return_value = mock_task

        result = await update_task_mcp(
            task_id=1,
            title="Updated Title",
            authorization=valid_authorization
        )

        validate_success_response_structure(result)
        validate_task_object(result["data"])
        assert result["metadata"]["tool"] == "update_task"
        assert result["metadata"]["task_id"] == 1

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.update_task')
    async def test_update_task_not_found_error(
        self, mock_update, mock_auth, mock_authenticated_user, valid_authorization
    ):
        """Contract: Non-existent task returns error."""
        mock_auth.return_value = mock_authenticated_user
        mock_update.return_value = None

        result = await update_task_mcp(
            task_id=99999,
            title="Should Fail",
            authorization=valid_authorization
        )

        validate_error_response_structure(result)
        assert "not found" in result["error"].lower() or "denied" in result["error"].lower()

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.update_task')
    async def test_update_task_returns_updated_values(
        self, mock_update, mock_auth, mock_authenticated_user, mock_task, valid_authorization
    ):
        """Contract: Response contains the updated field values."""
        mock_auth.return_value = mock_authenticated_user
        mock_task.title = "Brand New Title"
        mock_task.description = "Brand New Description"
        mock_task.dict.return_value["title"] = "Brand New Title"
        mock_task.dict.return_value["description"] = "Brand New Description"
        mock_update.return_value = mock_task

        result = await update_task_mcp(
            task_id=1,
            title="Brand New Title",
            description="Brand New Description",
            authorization=valid_authorization
        )

        validate_success_response_structure(result)
        assert result["data"]["title"] == "Brand New Title"
        assert result["data"]["description"] == "Brand New Description"

    # -------------------------------------------------------------------------
    # Authentication Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    async def test_update_task_requires_authorization(self, mock_auth):
        """Contract: Tool requires valid JWT in Authorization header."""
        from fastapi import HTTPException
        mock_auth.side_effect = HTTPException(status_code=401, detail="Authentication required")

        result = await update_task_mcp(task_id=1, title="Test", authorization=None)

        validate_error_response_structure(result)

    # -------------------------------------------------------------------------
    # User Scoping Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.update_task')
    async def test_update_task_user_scoped(
        self, mock_update, mock_auth, mock_authenticated_user, mock_task, valid_authorization
    ):
        """Contract: Can only update tasks belonging to authenticated user."""
        mock_auth.return_value = mock_authenticated_user
        mock_update.return_value = mock_task

        result = await update_task_mcp(
            task_id=1,
            title="Updated",
            authorization=valid_authorization
        )

        mock_update.assert_called_once()
        call_kwargs = mock_update.call_args
        assert call_kwargs.kwargs["user_id"] == mock_authenticated_user.user_id


# =============================================================================
# Error Response Format Consistency Tests
# =============================================================================

class TestErrorResponseConsistency:
    """Tests to verify all tools return consistent error response formats."""

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    async def test_auth_error_format_add_task(self, mock_auth):
        """Verify add_task returns consistent error format for auth failures."""
        from fastapi import HTTPException
        mock_auth.side_effect = HTTPException(status_code=401, detail="Authentication required")

        result = await add_task(title="Test", authorization=None)

        validate_error_response_structure(result)
        assert result["metadata"]["tool"] == "add_task"

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    async def test_auth_error_format_list_tasks(self, mock_auth):
        """Verify list_tasks returns consistent error format for auth failures."""
        from fastapi import HTTPException
        mock_auth.side_effect = HTTPException(status_code=401, detail="Authentication required")

        result = await list_tasks(authorization=None)

        validate_error_response_structure(result)
        assert result["metadata"]["tool"] == "list_tasks"

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    async def test_auth_error_format_complete_task(self, mock_auth):
        """Verify complete_task returns consistent error format for auth failures."""
        from fastapi import HTTPException
        mock_auth.side_effect = HTTPException(status_code=401, detail="Authentication required")

        result = await complete_task(task_id=1, authorization=None)

        validate_error_response_structure(result)
        assert result["metadata"]["tool"] == "complete_task"

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    async def test_auth_error_format_delete_task(self, mock_auth):
        """Verify delete_task returns consistent error format for auth failures."""
        from fastapi import HTTPException
        mock_auth.side_effect = HTTPException(status_code=401, detail="Authentication required")

        result = await delete_task_mcp(task_id=1, authorization=None)

        validate_error_response_structure(result)
        assert result["metadata"]["tool"] == "delete_task"

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    async def test_auth_error_format_update_task(self, mock_auth):
        """Verify update_task returns consistent error format for auth failures."""
        from fastapi import HTTPException
        mock_auth.side_effect = HTTPException(status_code=401, detail="Authentication required")

        result = await update_task_mcp(task_id=1, title="Test", authorization=None)

        validate_error_response_structure(result)
        assert result["metadata"]["tool"] == "update_task"

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.create_task')
    async def test_database_error_format(
        self, mock_create, mock_auth, mock_authenticated_user, valid_authorization
    ):
        """Verify database errors return consistent error format."""
        mock_auth.return_value = mock_authenticated_user
        mock_create.side_effect = Exception("Database connection failed")

        result = await add_task(title="Test", authorization=valid_authorization)

        validate_error_response_structure(result)
        assert "Database connection failed" in result["error"]


# =============================================================================
# Metadata Contract Tests
# =============================================================================

class TestMetadataContract:
    """Tests to verify metadata is always present and correct."""

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.create_task')
    async def test_metadata_contains_user_id(
        self, mock_create, mock_auth, mock_authenticated_user, mock_task, valid_authorization
    ):
        """Verify metadata contains user_id for successful operations."""
        mock_auth.return_value = mock_authenticated_user
        mock_create.return_value = mock_task

        result = await add_task(title="Test", authorization=valid_authorization)

        assert result["metadata"]["user_id"] == mock_authenticated_user.user_id

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    async def test_metadata_unknown_user_on_auth_error(self, mock_auth):
        """Verify metadata contains 'unknown' user_id when auth fails."""
        from fastapi import HTTPException
        mock_auth.side_effect = HTTPException(status_code=401, detail="Authentication required")

        result = await add_task(title="Test", authorization=None)

        assert result["metadata"]["user_id"] == "unknown"

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.create_task')
    async def test_metadata_contains_timestamp(
        self, mock_create, mock_auth, mock_authenticated_user, mock_task, valid_authorization
    ):
        """Verify metadata contains timestamp."""
        mock_auth.return_value = mock_authenticated_user
        mock_create.return_value = mock_task

        result = await add_task(title="Test", authorization=valid_authorization)

        assert "timestamp" in result["metadata"]
        assert result["metadata"]["timestamp"] is not None

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.get_tasks')
    async def test_metadata_contains_count_for_list(
        self, mock_get_tasks, mock_auth, mock_authenticated_user, mock_task, valid_authorization
    ):
        """Verify list_tasks metadata contains count."""
        mock_auth.return_value = mock_authenticated_user
        mock_get_tasks.return_value = [mock_task]

        result = await list_tasks(authorization=valid_authorization)

        assert "count" in result["metadata"]
        assert result["metadata"]["count"] == 1

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.toggle_complete')
    async def test_metadata_contains_task_id_for_complete(
        self, mock_toggle, mock_auth, mock_authenticated_user, completed_task, valid_authorization
    ):
        """Verify complete_task metadata contains task_id."""
        mock_auth.return_value = mock_authenticated_user
        mock_toggle.return_value = completed_task

        result = await complete_task(task_id=2, authorization=valid_authorization)

        assert "task_id" in result["metadata"]
        assert result["metadata"]["task_id"] == 2
