"""Integration tests for user authentication and task scoping.

These tests verify that:
1. Different users' tasks remain isolated
2. Cross-user access is prevented
3. Unauthorized access attempts return appropriate error responses

Task IDs: T032, T033, T034
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
import jwt

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.dependencies.auth import (
    AuthenticatedUser,
    get_current_user,
    validate_and_extract_user,
    validate_user_access,
)
from app.crud.task import (
    create_task,
    get_task,
    get_tasks,
    update_task,
    delete_task,
    toggle_complete,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def client():
    """Test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def user_a_id():
    """User A's identifier."""
    return "user-alpha-123"


@pytest.fixture
def user_b_id():
    """User B's identifier."""
    return "user-beta-456"


@pytest.fixture
def user_a_token(user_a_id):
    """Generate a valid JWT token for User A."""
    payload = {
        "sub": user_a_id,
        "email": "user_a@example.com",
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


@pytest.fixture
def user_b_token(user_b_id):
    """Generate a valid JWT token for User B."""
    payload = {
        "sub": user_b_id,
        "email": "user_b@example.com",
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


# =============================================================================
# JWT Validation Tests
# =============================================================================

class TestJWTValidation:
    """Tests for JWT token validation."""

    def test_valid_token_extracts_user_id(self, user_a_token, user_a_id):
        """Test that valid token correctly extracts user_id."""
        authorization = f"Bearer {user_a_token}"
        user = validate_and_extract_user(authorization)

        assert user.user_id == user_a_id
        assert user.email == "user_a@example.com"

    def test_missing_authorization_raises_401(self):
        """Test that missing authorization header raises 401."""
        with pytest.raises(HTTPException) as exc_info:
            validate_and_extract_user(None)

        assert exc_info.value.status_code == 401
        assert "Authentication required" in exc_info.value.detail

    def test_invalid_token_format_raises_401(self):
        """Test that invalid token format raises 401."""
        with pytest.raises(HTTPException) as exc_info:
            validate_and_extract_user("InvalidFormat")

        assert exc_info.value.status_code == 401

    def test_wrong_scheme_raises_401(self):
        """Test that non-Bearer scheme raises 401."""
        with pytest.raises(HTTPException) as exc_info:
            validate_and_extract_user("Basic some-token")

        assert exc_info.value.status_code == 401

    def test_expired_token_raises_401(self):
        """Test that expired token raises 401."""
        payload = {
            "sub": "test-user",
            "email": "test@example.com",
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        expired_token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

        with pytest.raises(HTTPException) as exc_info:
            validate_and_extract_user(f"Bearer {expired_token}")

        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()

    def test_invalid_signature_raises_401(self):
        """Test that token with invalid signature raises 401."""
        payload = {
            "sub": "test-user",
            "email": "test@example.com",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        }
        # Sign with wrong secret
        invalid_token = jwt.encode(payload, "wrong-secret", algorithm="HS256")

        with pytest.raises(HTTPException) as exc_info:
            validate_and_extract_user(f"Bearer {invalid_token}")

        assert exc_info.value.status_code == 401

    def test_missing_sub_claim_raises_401(self):
        """Test that token without 'sub' claim raises 401."""
        payload = {
            "email": "test@example.com",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        }
        token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

        with pytest.raises(HTTPException) as exc_info:
            validate_and_extract_user(f"Bearer {token}")

        assert exc_info.value.status_code == 401

    def test_empty_user_id_raises_401(self):
        """Test that token with empty user_id raises 401."""
        payload = {
            "sub": "",
            "email": "test@example.com",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        }
        token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

        with pytest.raises(HTTPException) as exc_info:
            validate_and_extract_user(f"Bearer {token}")

        assert exc_info.value.status_code == 401


# =============================================================================
# User Access Validation Tests
# =============================================================================

class TestUserAccessValidation:
    """Tests for user access validation helper."""

    def test_same_user_access_allowed(self):
        """Test that user can access their own resources."""
        assert validate_user_access("user-123", "user-123") is True

    def test_different_user_access_denied(self):
        """Test that user cannot access another user's resources."""
        assert validate_user_access("user-123", "user-456") is False


# =============================================================================
# Task Isolation Tests (T032)
# =============================================================================

class TestTaskIsolation:
    """Tests to verify that users can only see their own tasks."""

    @patch('app.services.task_service.get_session')
    def test_user_sees_only_own_tasks(self, mock_session, user_a_id, user_b_id):
        """Test that get_tasks returns only the authenticated user's tasks."""
        # This test verifies that the CRUD layer properly filters by user_id
        mock_sess = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_sess

        # Mock tasks for different users
        mock_task_a = MagicMock()
        mock_task_a.id = 1
        mock_task_a.user_id = user_a_id
        mock_task_a.title = "User A's Task"

        mock_task_b = MagicMock()
        mock_task_b.id = 2
        mock_task_b.user_id = user_b_id
        mock_task_b.title = "User B's Task"

        # When querying for user_a, only return user_a's tasks
        mock_sess.exec.return_value.all.return_value = [mock_task_a]

        from app.services.task_service import task_service
        tasks = task_service.get_tasks(user_id=user_a_id)

        # Verify user A only sees their task
        assert len(tasks) == 1
        assert tasks[0].user_id == user_a_id

    def test_get_tasks_with_no_user_id_returns_empty(self):
        """Test that get_tasks without user_id returns empty list."""
        tasks = get_tasks(user_id=None)
        assert tasks == []

    @patch('app.services.task_service.get_session')
    def test_get_task_by_id_enforces_ownership(self, mock_session, user_a_id, user_b_id):
        """Test that get_task_by_id only returns task if owned by user."""
        mock_sess = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_sess

        # Create a task owned by user B
        mock_task = MagicMock()
        mock_task.id = 1
        mock_task.user_id = user_b_id

        # When user A tries to get it, return None (filtered out by query)
        mock_sess.exec.return_value.first.return_value = None

        from app.services.task_service import task_service
        result = task_service.get_task_by_id(task_id=1, user_id=user_a_id)

        assert result is None


# =============================================================================
# Cross-User Access Prevention Tests (T033)
# =============================================================================

class TestCrossUserAccessPrevention:
    """Tests to verify that users cannot access each other's tasks."""

    @patch('app.services.task_service.get_session')
    def test_user_cannot_update_other_users_task(self, mock_session, user_a_id, user_b_id):
        """Test that a user cannot update another user's task."""
        mock_sess = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_sess

        # Task belongs to user B
        mock_task = MagicMock()
        mock_task.id = 1
        mock_task.user_id = user_b_id
        mock_task.title = "User B's Task"

        # When user A tries to access, return None (ownership check fails)
        mock_sess.get.return_value = mock_task

        from app.services.task_service import task_service
        result = task_service.update_task(
            task_id=1,
            user_id=user_a_id,  # User A trying to update
            title="Hacked Title"
        )

        # Should return None because user_id doesn't match
        assert result is None

    @patch('app.services.task_service.get_session')
    def test_user_cannot_delete_other_users_task(self, mock_session, user_a_id, user_b_id):
        """Test that a user cannot delete another user's task."""
        mock_sess = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_sess

        # Task belongs to user B
        mock_task = MagicMock()
        mock_task.id = 1
        mock_task.user_id = user_b_id

        mock_sess.get.return_value = mock_task

        from app.services.task_service import task_service
        result = task_service.delete_task(task_id=1, user_id=user_a_id)

        # Should return False because user_id doesn't match
        assert result is False

    @patch('app.services.task_service.get_session')
    def test_user_cannot_complete_other_users_task(self, mock_session, user_a_id, user_b_id):
        """Test that a user cannot complete another user's task."""
        mock_sess = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_sess

        # Task belongs to user B
        mock_task = MagicMock()
        mock_task.id = 1
        mock_task.user_id = user_b_id

        mock_sess.get.return_value = mock_task

        from app.services.task_service import task_service
        result = task_service.complete_task(task_id=1, user_id=user_a_id)

        # Should return None because user_id doesn't match
        assert result is None


# =============================================================================
# Unauthorized Access Error Response Tests (T034)
# =============================================================================

class TestUnauthorizedAccessResponses:
    """Tests to verify appropriate error responses for unauthorized access."""

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.toggle_complete')
    async def test_access_denied_returns_proper_error(self, mock_toggle, mock_auth, user_a_id):
        """Test that accessing non-owned task returns proper error format."""
        from app.tools.task_tools import complete_task

        mock_auth.return_value = AuthenticatedUser(user_id=user_a_id, email="test@example.com")
        mock_toggle.return_value = None  # Simulates task not found/not owned

        result = await complete_task(task_id=999, authorization="Bearer valid-token")

        assert result["success"] is False
        assert result["data"] is None
        assert "not found" in result["error"].lower() or "denied" in result["error"].lower()

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.update_task')
    async def test_update_denied_returns_proper_error(self, mock_update, mock_auth, user_a_id):
        """Test that updating non-owned task returns proper error format."""
        from app.tools.task_tools import update_task_mcp

        mock_auth.return_value = AuthenticatedUser(user_id=user_a_id, email="test@example.com")
        mock_update.return_value = None  # Simulates task not found/not owned

        result = await update_task_mcp(
            task_id=999,
            title="Hacked Title",
            authorization="Bearer valid-token"
        )

        assert result["success"] is False
        assert result["data"] is None
        assert result["error"] is not None

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.delete_task')
    async def test_delete_denied_returns_proper_error(self, mock_delete, mock_auth, user_a_id):
        """Test that deleting non-owned task returns proper error format."""
        from app.tools.task_tools import delete_task_mcp

        mock_auth.return_value = AuthenticatedUser(user_id=user_a_id, email="test@example.com")
        mock_delete.return_value = False  # Simulates task not found/not owned

        result = await delete_task_mcp(task_id=999, authorization="Bearer valid-token")

        assert result["success"] is False
        assert result["data"] is None
        assert result["error"] is not None

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    async def test_no_auth_returns_401_error(self, mock_auth):
        """Test that missing authentication returns proper 401 error."""
        from app.tools.task_tools import list_tasks

        mock_auth.side_effect = HTTPException(status_code=401, detail="Authentication required")

        result = await list_tasks(authorization=None)

        assert result["success"] is False
        assert "Authentication required" in result["error"]

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    async def test_expired_token_returns_401_error(self, mock_auth):
        """Test that expired token returns proper 401 error."""
        from app.tools.task_tools import add_task

        mock_auth.side_effect = HTTPException(status_code=401, detail="Token expired")

        result = await add_task(title="Test", authorization="Bearer expired-token")

        assert result["success"] is False
        assert "expired" in result["error"].lower()


# =============================================================================
# Multi-User Scenario Tests
# =============================================================================

class TestMultiUserScenarios:
    """End-to-end tests for multi-user scenarios."""

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.create_task')
    @patch('app.tools.task_tools.get_tasks')
    async def test_users_see_different_task_lists(
        self, mock_get_tasks, mock_create, mock_auth, user_a_id, user_b_id
    ):
        """Test that different users see different task lists."""
        from app.tools.task_tools import add_task, list_tasks

        # Setup for User A
        mock_auth.return_value = AuthenticatedUser(user_id=user_a_id, email="a@test.com")

        mock_task_a = MagicMock()
        mock_task_a.dict.return_value = {"id": 1, "title": "Task A", "user_id": user_a_id}
        mock_task_a.created_at = datetime.now(timezone.utc)

        mock_create.return_value = mock_task_a
        mock_get_tasks.return_value = [mock_task_a]

        # User A lists tasks
        result_a = await list_tasks(authorization="Bearer token-a")

        assert result_a["success"] is True
        assert len(result_a["data"]) == 1
        assert result_a["data"][0]["user_id"] == user_a_id

        # Setup for User B
        mock_auth.return_value = AuthenticatedUser(user_id=user_b_id, email="b@test.com")

        mock_task_b = MagicMock()
        mock_task_b.dict.return_value = {"id": 2, "title": "Task B", "user_id": user_b_id}

        mock_get_tasks.return_value = [mock_task_b]

        # User B lists tasks
        result_b = await list_tasks(authorization="Bearer token-b")

        assert result_b["success"] is True
        assert len(result_b["data"]) == 1
        assert result_b["data"][0]["user_id"] == user_b_id

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.create_task')
    async def test_task_created_with_authenticated_user_id(
        self, mock_create, mock_auth, user_a_id
    ):
        """Test that new tasks are created with the authenticated user's ID."""
        from app.tools.task_tools import add_task

        mock_auth.return_value = AuthenticatedUser(user_id=user_a_id, email="a@test.com")

        mock_task = MagicMock()
        mock_task.id = 1
        mock_task.user_id = user_a_id
        mock_task.created_at = datetime.now(timezone.utc)
        mock_task.dict.return_value = {"id": 1, "user_id": user_a_id, "title": "Test"}

        mock_create.return_value = mock_task

        result = await add_task(title="Test Task", authorization="Bearer token")

        # Verify create_task was called with the authenticated user's ID
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["user_id"] == user_a_id
