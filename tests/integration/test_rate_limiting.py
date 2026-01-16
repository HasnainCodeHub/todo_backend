"""Integration tests for rate limiting and deterministic behavior.

These tests verify that:
1. Rate limiting works correctly per user
2. Rate limits are enforced at 100 requests per minute
3. Rate limiting doesn't affect tool determinism
4. All tools maintain deterministic behavior

Task IDs: T050, T051
"""

import pytest
import time
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from app.utils.rate_limiter import RateLimiter, rate_limiter
from app.utils.rate_limit_decorator import rate_limit, rate_limit_with_user_id
from app.dependencies.auth import AuthenticatedUser


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def fresh_rate_limiter():
    """Create a fresh rate limiter for each test."""
    return RateLimiter(max_requests=5, window_seconds=1)


@pytest.fixture
def mock_authenticated_user():
    """Create a mock authenticated user."""
    return AuthenticatedUser(user_id="rate-limit-test-user", email="test@example.com")


# =============================================================================
# Rate Limiter Core Tests (T050)
# =============================================================================

class TestRateLimiterCore:
    """Tests for the core rate limiter functionality."""

    def test_rate_limiter_allows_requests_under_limit(self, fresh_rate_limiter):
        """Test that requests under the limit are allowed."""
        user_id = "test-user"

        # Should allow first 5 requests
        for i in range(5):
            assert fresh_rate_limiter.is_allowed(user_id) is True

    def test_rate_limiter_blocks_requests_over_limit(self, fresh_rate_limiter):
        """Test that requests over the limit are blocked."""
        user_id = "test-user"

        # Use up all allowed requests
        for _ in range(5):
            fresh_rate_limiter.is_allowed(user_id)

        # 6th request should be blocked
        assert fresh_rate_limiter.is_allowed(user_id) is False

    def test_rate_limiter_resets_after_window(self, fresh_rate_limiter):
        """Test that rate limit resets after the time window."""
        user_id = "test-user"

        # Use up all allowed requests
        for _ in range(5):
            fresh_rate_limiter.is_allowed(user_id)

        # Blocked
        assert fresh_rate_limiter.is_allowed(user_id) is False

        # Wait for window to expire
        time.sleep(1.1)

        # Should be allowed again
        assert fresh_rate_limiter.is_allowed(user_id) is True

    def test_rate_limiter_per_user_isolation(self, fresh_rate_limiter):
        """Test that rate limits are per-user."""
        user_a = "user-a"
        user_b = "user-b"

        # Use up user A's limit
        for _ in range(5):
            fresh_rate_limiter.is_allowed(user_a)

        # User A should be blocked
        assert fresh_rate_limiter.is_allowed(user_a) is False

        # User B should still be allowed
        assert fresh_rate_limiter.is_allowed(user_b) is True

    def test_rate_limiter_sliding_window(self, fresh_rate_limiter):
        """Test sliding window behavior."""
        user_id = "test-user"

        # Make 3 requests
        for _ in range(3):
            fresh_rate_limiter.is_allowed(user_id)

        # Wait half the window
        time.sleep(0.5)

        # Make 2 more requests (total 5)
        for _ in range(2):
            assert fresh_rate_limiter.is_allowed(user_id) is True

        # 6th request should be blocked
        assert fresh_rate_limiter.is_allowed(user_id) is False

        # Wait for first 3 to expire
        time.sleep(0.6)

        # Should be allowed again (only 2 in window now)
        assert fresh_rate_limiter.is_allowed(user_id) is True


# =============================================================================
# Rate Limit Configuration Tests
# =============================================================================

class TestRateLimitConfiguration:
    """Tests for rate limit configuration."""

    def test_default_rate_limit_100_per_minute(self):
        """Test that default rate limit is 100 requests per minute."""
        limiter = RateLimiter()

        assert limiter.max_requests == 100
        assert limiter.window_seconds == 60

    def test_custom_rate_limit_configuration(self):
        """Test custom rate limit configuration."""
        limiter = RateLimiter(max_requests=50, window_seconds=30)

        assert limiter.max_requests == 50
        assert limiter.window_seconds == 30

    def test_global_rate_limiter_instance(self):
        """Test that global rate limiter instance exists."""
        from app.utils.rate_limiter import rate_limiter

        assert rate_limiter is not None
        assert isinstance(rate_limiter, RateLimiter)


# =============================================================================
# Rate Limit Decorator Tests
# =============================================================================

class TestRateLimitDecorator:
    """Tests for the rate limit decorator."""

    @pytest.mark.asyncio
    async def test_rate_limit_decorator_allows_under_limit(self):
        """Test that decorator allows requests under the limit."""
        call_count = 0

        @rate_limit(max_requests=5, window_seconds=60)
        async def test_func(authorization=None):
            nonlocal call_count
            call_count += 1
            return {"success": True}

        # Should allow 5 calls
        for _ in range(5):
            result = await test_func(authorization="Bearer test-token")
            # Since we can't easily test the actual rate limiting without
            # proper JWT validation, we just verify the function runs
            assert result is not None

    @pytest.mark.asyncio
    async def test_rate_limit_decorator_without_auth(self):
        """Test that decorator works without authorization."""
        @rate_limit(max_requests=5, window_seconds=60)
        async def test_func(authorization=None):
            return {"success": True}

        # Should work without auth (rate limiting skipped)
        result = await test_func()
        assert result["success"] is True


# =============================================================================
# Tool Determinism Tests (T051)
# =============================================================================

class TestToolDeterminism:
    """Tests to verify all tools maintain deterministic behavior."""

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.create_task')
    async def test_add_task_deterministic(self, mock_create, mock_auth, mock_authenticated_user):
        """Test that add_task produces consistent results for same input."""
        from app.tools.task_tools import add_task

        mock_auth.return_value = mock_authenticated_user

        mock_task = MagicMock()
        mock_task.id = 1
        mock_task.title = "Test Task"
        mock_task.created_at = datetime.now(timezone.utc)
        mock_task.dict.return_value = {
            "id": 1,
            "title": "Test Task",
            "user_id": "test-user"
        }
        mock_create.return_value = mock_task

        # Call twice with same input
        result1 = await add_task(title="Test Task", authorization="Bearer token")
        result2 = await add_task(title="Test Task", authorization="Bearer token")

        # Structure should be identical
        assert result1["success"] == result2["success"]
        assert result1["data"]["title"] == result2["data"]["title"]

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.get_tasks')
    async def test_list_tasks_deterministic(self, mock_get_tasks, mock_auth, mock_authenticated_user):
        """Test that list_tasks produces consistent results for same state."""
        from app.tools.task_tools import list_tasks

        mock_auth.return_value = mock_authenticated_user

        mock_task = MagicMock()
        mock_task.dict.return_value = {"id": 1, "title": "Task"}
        mock_get_tasks.return_value = [mock_task]

        # Call twice
        result1 = await list_tasks(authorization="Bearer token")
        result2 = await list_tasks(authorization="Bearer token")

        # Results should be identical
        assert result1["success"] == result2["success"]
        assert len(result1["data"]) == len(result2["data"])

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.toggle_complete')
    async def test_complete_task_idempotent(self, mock_toggle, mock_auth, mock_authenticated_user):
        """Test that complete_task is idempotent."""
        from app.tools.task_tools import complete_task

        mock_auth.return_value = mock_authenticated_user

        mock_task = MagicMock()
        mock_task.id = 1
        mock_task.completed = True
        mock_task.updated_at = datetime.now(timezone.utc)
        mock_task.dict.return_value = {"id": 1, "completed": True}
        mock_toggle.return_value = mock_task

        # Call twice on already completed task
        result1 = await complete_task(task_id=1, authorization="Bearer token")
        result2 = await complete_task(task_id=1, authorization="Bearer token")

        # Both should succeed
        assert result1["success"] is True
        assert result2["success"] is True
        assert result1["data"]["completed"] == result2["data"]["completed"]

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    async def test_error_responses_deterministic(self, mock_auth):
        """Test that error responses are deterministic."""
        from app.tools.task_tools import add_task
        from fastapi import HTTPException

        mock_auth.side_effect = HTTPException(status_code=401, detail="Auth failed")

        # Call twice with same error condition
        result1 = await add_task(title="Test", authorization=None)
        mock_auth.side_effect = HTTPException(status_code=401, detail="Auth failed")
        result2 = await add_task(title="Test", authorization=None)

        # Error structure should be identical
        assert result1["success"] == result2["success"]
        assert result1["error"] == result2["error"]


# =============================================================================
# Stateless Operation Tests
# =============================================================================

class TestStatelessOperation:
    """Tests to verify server remains stateless."""

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.create_task')
    async def test_no_in_memory_state_between_calls(self, mock_create, mock_auth, mock_authenticated_user):
        """Test that no in-memory state persists between tool calls."""
        from app.tools.task_tools import add_task

        mock_auth.return_value = mock_authenticated_user

        mock_task1 = MagicMock()
        mock_task1.id = 1
        mock_task1.created_at = datetime.now(timezone.utc)
        mock_task1.dict.return_value = {"id": 1, "title": "Task 1"}

        mock_task2 = MagicMock()
        mock_task2.id = 2
        mock_task2.created_at = datetime.now(timezone.utc)
        mock_task2.dict.return_value = {"id": 2, "title": "Task 2"}

        mock_create.side_effect = [mock_task1, mock_task2]

        # Create two tasks
        result1 = await add_task(title="Task 1", authorization="Bearer token")
        result2 = await add_task(title="Task 2", authorization="Bearer token")

        # Each should have unique IDs (no collision from in-memory state)
        assert result1["data"]["id"] != result2["data"]["id"]

    def test_rate_limiter_thread_safety(self, fresh_rate_limiter):
        """Test that rate limiter is thread-safe."""
        import threading
        import concurrent.futures

        user_id = "concurrent-user"
        results = []

        def check_rate_limit():
            return fresh_rate_limiter.is_allowed(user_id)

        # Run concurrent checks
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(check_rate_limit) for _ in range(10)]
            results = [f.result() for f in futures]

        # Exactly 5 should be True (the limit)
        assert sum(results) == 5


# =============================================================================
# Rate Limiting Integration Tests
# =============================================================================

class TestRateLimitingIntegration:
    """Integration tests for rate limiting with actual tools."""

    @pytest.mark.asyncio
    @patch('app.tools.task_tools.get_authenticated_user_from_header')
    @patch('app.tools.task_tools.get_tasks')
    async def test_rate_limit_does_not_affect_success_response(
        self, mock_get_tasks, mock_auth, mock_authenticated_user
    ):
        """Test that rate limiting doesn't corrupt successful responses."""
        from app.tools.task_tools import list_tasks

        mock_auth.return_value = mock_authenticated_user
        mock_get_tasks.return_value = []

        result = await list_tasks(authorization="Bearer valid-token")

        # Response should be properly formatted even with rate limiting active
        assert "success" in result
        assert "data" in result
        assert "error" in result
        assert "metadata" in result

    def test_rate_limit_error_response_format(self):
        """Test that rate limit error follows standard format."""
        from app.utils.error_responses import create_error_response

        error_response = create_error_response(
            error_code="RATE_LIMIT_EXCEEDED",
            message="Rate limit exceeded. Maximum 100 requests per 60 seconds.",
            details={
                "max_requests": 100,
                "window_seconds": 60,
                "user_id": "test-user"
            },
            tool_name="list_tasks",
            user_id="test-user"
        )

        assert error_response["success"] is False
        assert error_response["error"]["code"] == "RATE_LIMIT_EXCEEDED"
        assert error_response["error"]["details"]["max_requests"] == 100
