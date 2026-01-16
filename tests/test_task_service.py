"""Tests for the enhanced TaskService with transaction handling and connection resilience."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
from sqlalchemy.exc import OperationalError
from app.services.task_service import TaskService
from app.models.task import Task


class TestTaskService:
    """Test cases for the enhanced TaskService."""

    def setup_method(self):
        """Setup test fixtures before each test method."""
        self.task_service = TaskService(max_retries=2, retry_delay=0.1)

    @patch('app.services.task_service.get_session')
    def test_create_task_success(self, mock_get_session):
        """Test successful task creation."""
        # Mock session
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session

        # Mock task object
        mock_task = MagicMock(spec=Task)
        mock_task.id = 1
        mock_task.title = "Test Task"
        mock_task.description = "Test Description"
        mock_task.user_id = "user123"
        mock_task.completed = False
        mock_task.created_at = datetime.utcnow()
        mock_task.updated_at = datetime.utcnow()

        # Configure session to return the mock task
        mock_session.add.return_value = None
        mock_session.commit.return_value = None
        mock_session.refresh.return_value = None

        # Call the method
        result = self.task_service.create_task(
            title="Test Task",
            description="Test Description",
            user_id="user123"
        )

        # Assertions
        assert result is not None
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    @patch('app.services.task_service.get_session')
    def test_create_task_with_retry_on_operational_error(self, mock_get_session):
        """Test that task creation retries on operational errors."""
        # Mock session to raise OperationalError on first call, succeed on second
        mock_session_fail = MagicMock()
        mock_session_fail.add.side_effect = OperationalError("statement", {}, Exception("connection failed"))
        mock_session_fail.commit.side_effect = OperationalError("statement", {}, Exception("connection failed"))
        mock_session_fail.rollback.return_value = None

        mock_session_success = MagicMock()
        mock_task = MagicMock(spec=Task)
        mock_task.id = 1
        mock_task.title = "Test Task"
        mock_task.description = "Test Description"
        mock_task.user_id = "user123"
        mock_task.completed = False
        mock_task.created_at = datetime.utcnow()
        mock_task.updated_at = datetime.utcnow()

        mock_session_success.add.return_value = None
        mock_session_success.commit.return_value = None
        mock_session_success.refresh.return_value = None

        # Configure the mock to fail first, then succeed
        mock_get_session.return_value.__enter__.side_effect = [
            mock_session_fail,  # First call fails
            mock_session_success  # Second call succeeds
        ]

        # Call the method - should succeed after retry
        result = self.task_service.create_task(
            title="Test Task",
            description="Test Description",
            user_id="user123"
        )

        # Assertions
        assert result is not None
        assert mock_session_fail.add.call_count == 1
        assert mock_session_success.add.call_count == 1

    @patch('app.services.task_service.get_session')
    def test_get_tasks_with_status_filter(self, mock_get_session):
        """Test getting tasks with status filter."""
        # Mock session
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session

        # Mock tasks
        mock_task1 = MagicMock(spec=Task)
        mock_task1.id = 1
        mock_task1.title = "Task 1"
        mock_task1.completed = False

        mock_task2 = MagicMock(spec=Task)
        mock_task2.id = 2
        mock_task2.title = "Task 2"
        mock_task2.completed = True

        mock_session.exec.return_value.all.return_value = [mock_task1, mock_task2]

        # Call the method
        result = self.task_service.get_tasks(user_id="user123", status="pending")

        # Assertions
        assert len(result) == 2
        mock_session.exec.assert_called_once()

    @patch('app.services.task_service.get_session')
    def test_update_task_success(self, mock_get_session):
        """Test successful task update."""
        # Mock session
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session

        # Mock task
        mock_task = MagicMock(spec=Task)
        mock_task.id = 1
        mock_task.title = "Updated Task"
        mock_task.user_id = "user123"
        mock_task.completed = False
        mock_task.updated_at = datetime.utcnow()

        mock_session.get.return_value = mock_task
        mock_session.add.return_value = None
        mock_session.commit.return_value = None
        mock_session.refresh.return_value = None

        # Call the method
        result = self.task_service.update_task(
            task_id=1,
            user_id="user123",
            title="Updated Task"
        )

        # Assertions
        assert result is not None
        assert result.title == "Updated Task"
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    @patch('app.services.task_service.get_session')
    def test_delete_task_success(self, mock_get_session):
        """Test successful task deletion."""
        # Mock session
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session

        # Mock task
        mock_task = MagicMock(spec=Task)
        mock_task.id = 1
        mock_task.user_id = "user123"

        mock_session.get.return_value = mock_task
        mock_session.delete.return_value = None
        mock_session.commit.return_value = None

        # Call the method
        result = self.task_service.delete_task(task_id=1, user_id="user123")

        # Assertions
        assert result is True
        mock_session.delete.assert_called_once_with(mock_task)
        mock_session.commit.assert_called_once()

    @patch('app.services.task_service.get_session')
    def test_bulk_update_tasks(self, mock_get_session):
        """Test bulk update of tasks."""
        # Mock session
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session

        # Mock tasks
        mock_task1 = MagicMock(spec=Task)
        mock_task1.id = 1
        mock_task1.user_id = "user123"
        mock_task1.title = "Original Task 1"

        mock_task2 = MagicMock(spec=Task)
        mock_task2.id = 2
        mock_task2.user_id = "user123"
        mock_task2.title = "Original Task 2"

        mock_session.exec.return_value.all.return_value = [mock_task1, mock_task2]
        mock_session.add.return_value = None
        mock_session.commit.return_value = None

        # Call the method
        result = self.task_service.bulk_update_tasks(
            task_ids=[1, 2],
            user_id="user123",
            title="Updated Title"
        )

        # Assertions
        assert result == 2  # Two tasks updated
        assert mock_session.add.call_count == 2  # Called for each task
        mock_session.commit.assert_called_once()

    def test_task_service_initialization(self):
        """Test TaskService initialization."""
        service = TaskService(max_retries=5, retry_delay=0.5)

        assert service.max_retries == 5
        assert service.retry_delay == 0.5