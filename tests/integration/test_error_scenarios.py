"""Integration tests for error scenarios.

These tests verify that:
1. All error responses follow the standardized format
2. Different error types are handled correctly
3. Error messages are informative and consistent

Task ID: T046
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError, OperationalError

from app.dependencies.auth import AuthenticatedUser
from app.tools.task_tools import (
    add_task,
    list_tasks,
    complete_task,
    update_task_mcp,
    delete_task_mcp,
    get_task_stats_mcp,
    bulk_update_tasks_mcp,
)
from app.utils.error_responses import (
    create_error_response,
    handle_mcp_tool_error,
    validate_required_fields,
    validate_string_field,
    validate_task_data,
    validate_task_id,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_authenticated_user():
    """Create a mock authenticated user."""
    return AuthenticatedUser(user_id="error-test-user", email="test@example.com")


# =============================================================================
# Error Response Format Tests
# =============================================================================

class TestErrorResponseFormat:
    """Tests for standardized error response format."""

    def test_create_error_response_structure(self):
        """Test that create_error_response returns correct structure."""
        response = create_error_response(
            error_code="TEST_ERROR",
            message="Test error message",
            details={"key": "value"},
            user_id="user-123",
            tool_name="test_tool"
        )

        # Verify top-level structure
        assert "success" in response
        assert "data" in response
        assert "error" in response
        assert "metadata" in response

        # Verify success is False
        assert response["success"] is False

        # Verify data is None
        assert response["data"] is None

        # Verify error structure
        assert "code" in response["error"]
        assert "message" in response["error"]
        assert "details" in response["error"]
        assert response["error"]["code"] == "TEST_ERROR"
        assert response["error"]["message"] == "Test error message"

        # Verify metadata
        assert response["metadata"]["tool"] == "test_tool"
        assert response["metadata"]["user_id"] == "user-123"
        assert "timestamp" in response["metadata"]

    def test_error_response_with_minimal_params(self):
        """Test error response with only required parameters."""
        response = create_error_response(
            error_code="MINIMAL_ERROR",
            message="Minimal error"
        )

        assert response["success"] is False
        assert response["error"]["code"] == "MINIMAL_ERROR"
        assert response["error"]["details"] == {}
        assert response["metadata"]["user_id"] == "unknown"
        assert response["metadata"]["tool"] == "unknown"


# =============================================================================
# Authentication Error Tests
# =============================================================================

class TestAuthenticationErrors:
    """Tests for authentication-related errors."""

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    async def test_missing_auth_header_error(self, mock_auth):
        """Test error when Authorization header is missing."""
        mock_auth.side_effect = HTTPException(status_code=401, detail="Authentication required")

        result = await add_task(title="Test", authorization=None)

        assert result["success"] is False
        assert "Authentication required" in result["error"]
        assert result["metadata"]["user_id"] == "unknown"

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    async def test_invalid_token_error(self, mock_auth):
        """Test error when JWT token is invalid."""
        mock_auth.side_effect = HTTPException(status_code=401, detail="Invalid token")

        result = await list_tasks(authorization="Bearer invalid.token.here")

        assert result["success"] is False
        assert "Invalid token" in result["error"]

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    async def test_expired_token_error(self, mock_auth):
        """Test error when JWT token is expired."""
        mock_auth.side_effect = HTTPException(status_code=401, detail="Token expired")

        result = await complete_task(task_id=1, authorization="Bearer expired.token")

        assert result["success"] is False
        assert "expired" in result["error"].lower()

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    async def test_malformed_auth_header_error(self, mock_auth):
        """Test error when Authorization header format is wrong."""
        mock_auth.side_effect = HTTPException(
            status_code=401,
            detail="Invalid authorization header format"
        )

        result = await delete_task_mcp(task_id=1, authorization="InvalidFormat")

        assert result["success"] is False
        assert "authorization" in result["error"].lower() or "format" in result["error"].lower()


# =============================================================================
# Not Found Error Tests
# =============================================================================

class TestNotFoundErrors:
    """Tests for resource not found errors."""

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.toggle_complete')
    async def test_complete_nonexistent_task_error(self, mock_toggle, mock_auth, mock_authenticated_user):
        """Test error when completing non-existent task."""
        mock_auth.return_value = mock_authenticated_user
        mock_toggle.return_value = None

        result = await complete_task(task_id=99999, authorization="Bearer valid-token")

        assert result["success"] is False
        assert result["data"] is None
        assert "not found" in result["error"].lower() or "denied" in result["error"].lower()

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.update_task')
    async def test_update_nonexistent_task_error(self, mock_update, mock_auth, mock_authenticated_user):
        """Test error when updating non-existent task."""
        mock_auth.return_value = mock_authenticated_user
        mock_update.return_value = None

        result = await update_task_mcp(
            task_id=99999,
            title="Updated",
            authorization="Bearer valid-token"
        )

        assert result["success"] is False
        assert result["data"] is None
        assert "not found" in result["error"].lower() or "denied" in result["error"].lower()

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.delete_task')
    async def test_delete_nonexistent_task_error(self, mock_delete, mock_auth, mock_authenticated_user):
        """Test error when deleting non-existent task."""
        mock_auth.return_value = mock_authenticated_user
        mock_delete.return_value = False

        result = await delete_task_mcp(task_id=99999, authorization="Bearer valid-token")

        assert result["success"] is False
        assert result["data"] is None
        assert "not found" in result["error"].lower() or "denied" in result["error"].lower()


# =============================================================================
# Database Error Tests
# =============================================================================

class TestDatabaseErrors:
    """Tests for database-related errors."""

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.create_task')
    async def test_database_connection_error(self, mock_create, mock_auth, mock_authenticated_user):
        """Test error when database connection fails."""
        mock_auth.return_value = mock_authenticated_user
        mock_create.side_effect = OperationalError("statement", {}, Exception("Connection refused"))

        result = await add_task(title="Test", authorization="Bearer valid-token")

        assert result["success"] is False
        assert result["error"] is not None

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.get_tasks')
    async def test_database_query_error(self, mock_get_tasks, mock_auth, mock_authenticated_user):
        """Test error when database query fails."""
        mock_auth.return_value = mock_authenticated_user
        mock_get_tasks.side_effect = SQLAlchemyError("Query failed")

        result = await list_tasks(authorization="Bearer valid-token")

        assert result["success"] is False
        assert result["error"] is not None


# =============================================================================
# Validation Error Tests
# =============================================================================

class TestValidationErrors:
    """Tests for input validation errors."""

    def test_validate_required_fields_missing(self):
        """Test validation when required fields are missing."""
        result = validate_required_fields(
            data={"title": "Test"},
            required_fields=["title", "user_id"]
        )

        assert result["valid"] is False
        assert "user_id" in result["missing_fields"]

    def test_validate_required_fields_empty_string(self):
        """Test validation when required field is empty string."""
        result = validate_required_fields(
            data={"title": "", "user_id": "123"},
            required_fields=["title", "user_id"]
        )

        assert result["valid"] is False
        assert "title" in result["missing_fields"]

    def test_validate_string_field_too_short(self):
        """Test validation when string is too short."""
        result = validate_string_field(
            value="",
            field_name="title",
            min_length=1,
            max_length=200
        )

        assert result["valid"] is False
        assert "at least" in result["message"]

    def test_validate_string_field_too_long(self):
        """Test validation when string is too long."""
        result = validate_string_field(
            value="x" * 201,
            field_name="title",
            min_length=1,
            max_length=200
        )

        assert result["valid"] is False
        assert "no more than" in result["message"]

    def test_validate_task_data_valid(self):
        """Test validation passes for valid task data."""
        result = validate_task_data(
            title="Valid Title",
            description="Valid description"
        )

        assert result["valid"] is True

    def test_validate_task_data_empty_title(self):
        """Test validation fails for empty title."""
        result = validate_task_data(
            title="",
            description="Description"
        )

        assert result["valid"] is False

    def test_validate_task_id_invalid(self):
        """Test validation fails for invalid task ID."""
        result = validate_task_id(0)

        assert result["valid"] is False
        assert "positive integer" in result["message"]

    def test_validate_task_id_none(self):
        """Test validation fails for None task ID."""
        result = validate_task_id(None)

        assert result["valid"] is False
        assert "required" in result["message"]


# =============================================================================
# MCP Tool Error Handler Tests
# =============================================================================

class TestMCPToolErrorHandler:
    """Tests for the MCP tool error handler."""

    def test_handle_value_error(self):
        """Test handling of ValueError."""
        error = ValueError("Invalid value provided")
        result = handle_mcp_tool_error(
            exception=error,
            tool_name="test_tool",
            user_id="user-123"
        )

        assert result["success"] is False
        assert result["error"]["code"] == "VALIDATION_ERROR"
        assert "Invalid value provided" in result["error"]["message"]

    def test_handle_permission_error(self):
        """Test handling of PermissionError."""
        error = PermissionError("Access denied")
        result = handle_mcp_tool_error(
            exception=error,
            tool_name="test_tool",
            user_id="user-123"
        )

        assert result["success"] is False
        assert result["error"]["code"] == "FORBIDDEN"

    def test_handle_not_found_error(self):
        """Test handling of FileNotFoundError."""
        error = FileNotFoundError("Resource not found")
        result = handle_mcp_tool_error(
            exception=error,
            tool_name="test_tool",
            user_id="user-123"
        )

        assert result["success"] is False
        assert result["error"]["code"] == "NOT_FOUND"

    def test_handle_generic_error(self):
        """Test handling of generic Exception."""
        error = Exception("Something went wrong")
        result = handle_mcp_tool_error(
            exception=error,
            tool_name="test_tool",
            user_id="user-123"
        )

        assert result["success"] is False
        assert result["error"]["code"] == "INTERNAL_ERROR"

    def test_error_handler_includes_details(self):
        """Test that error handler includes exception details."""
        error = ValueError("Test error")
        result = handle_mcp_tool_error(
            exception=error,
            tool_name="test_tool",
            user_id="user-123",
            additional_details={"task_id": 123}
        )

        assert "exception_type" in result["error"]["details"]
        assert result["error"]["details"]["exception_type"] == "ValueError"
        assert result["error"]["details"]["task_id"] == 123


# =============================================================================
# Error Consistency Across Tools Tests
# =============================================================================

class TestErrorConsistencyAcrossTools:
    """Tests to verify consistent error handling across all tools."""

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    async def test_all_tools_have_consistent_auth_error_format(self, mock_auth):
        """Test that all tools return consistent error format for auth failures."""
        mock_auth.side_effect = HTTPException(status_code=401, detail="Auth failed")

        tools_and_calls = [
            ("add_task", add_task(title="Test", authorization=None)),
            ("list_tasks", list_tasks(authorization=None)),
            ("complete_task", complete_task(task_id=1, authorization=None)),
            ("update_task", update_task_mcp(task_id=1, title="Test", authorization=None)),
            ("delete_task", delete_task_mcp(task_id=1, authorization=None)),
            ("get_task_stats", get_task_stats_mcp(authorization=None)),
            ("bulk_update_tasks", bulk_update_tasks_mcp(task_ids=[1], authorization=None)),
        ]

        for tool_name, coro in tools_and_calls:
            result = await coro

            # All should have consistent structure
            assert "success" in result, f"{tool_name} missing 'success'"
            assert result["success"] is False, f"{tool_name} should have success=False"
            assert "data" in result, f"{tool_name} missing 'data'"
            assert result["data"] is None, f"{tool_name} should have data=None"
            assert "error" in result, f"{tool_name} missing 'error'"
            assert result["error"] is not None, f"{tool_name} should have error"
            assert "metadata" in result, f"{tool_name} missing 'metadata'"

            # Reset mock for next iteration
            mock_auth.side_effect = HTTPException(status_code=401, detail="Auth failed")

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    async def test_metadata_always_present_on_error(self, mock_auth, mock_authenticated_user):
        """Test that metadata is always present even on errors."""
        mock_auth.return_value = mock_authenticated_user

        # Patch to cause an error
        with patch('app.tools.task_tools.create_task') as mock_create:
            mock_create.side_effect = Exception("Database error")

            result = await add_task(title="Test", authorization="Bearer token")

            assert "metadata" in result
            assert "tool" in result["metadata"]
            assert result["metadata"]["tool"] == "add_task"
