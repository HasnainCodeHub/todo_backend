"""Enhanced Task service for MCP Server with transaction handling and connection resilience."""

import asyncio
import logging
from typing import List, Optional
from contextlib import contextmanager
from datetime import datetime
from sqlmodel import select, Session
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential
from ..database import get_session
from ..models.task import Task, TaskUpdate

logger = logging.getLogger(__name__)
_UNSET = object()


class TaskService:
    """Enhanced service class for task-related business operations with transaction safety."""

    def __init__(self, max_retries: int = 3, retry_delay: float = 1.0):
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    @retry(
        retry=retry_if_exception_type((OperationalError, SQLAlchemyError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    def create_task(
        self,
        title: str,
        description: Optional[str],
        user_id: str,
        priority: str = "medium",
        due_date: Optional[datetime] = None,
        category: Optional[str] = None,
    ) -> Task:
        """
        Create a new task for a user with transaction safety and retry logic.

        Args:
            title: Task title
            description: Task description (optional)
            user_id: ID of the user creating the task

        Returns:
            Created Task object

        Raises:
            SQLAlchemyError: If database operation fails after retries
        """
        task = Task(
            title=title,
            description=description,
            priority=priority,
            due_date=due_date,
            category=category,
            user_id=user_id,
            completed=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        with get_session() as session:
            try:
                session.add(task)
                session.commit()
                session.refresh(task)

                logger.info(f"Task created successfully: {task.id} for user: {user_id}")
                return task
            except SQLAlchemyError as e:
                session.rollback()
                logger.error(f"Failed to create task for user {user_id}: {str(e)}")
                raise

    @retry(
        retry=retry_if_exception_type((OperationalError, SQLAlchemyError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    def get_tasks(self, user_id: str, status: str = "all") -> List[Task]:
        """
        Get tasks for a user filtered by status with connection resilience.

        Args:
            user_id: ID of the user whose tasks to retrieve
            status: Filter by status ('all', 'pending', 'completed')

        Returns:
            List of Task objects
        """
        with get_session() as session:
            try:
                query = select(Task).where(Task.user_id == user_id)

                if status == "pending":
                    query = query.where(Task.completed == False)
                elif status == "completed":
                    query = query.where(Task.completed == True)

                tasks = session.exec(query).all()
                logger.info(f"Retrieved {len(tasks)} tasks for user: {user_id}")
                return tasks
            except SQLAlchemyError as e:
                logger.error(f"Failed to retrieve tasks for user {user_id}: {str(e)}")
                raise

    @retry(
        retry=retry_if_exception_type((OperationalError, SQLAlchemyError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    def get_task_by_id(self, task_id: int, user_id: str) -> Optional[Task]:
        """
        Get a specific task by ID for a user with transaction safety.

        Args:
            task_id: ID of the task to retrieve
            user_id: ID of the user who owns the task

        Returns:
            Task object if found and owned by user, None otherwise
        """
        with get_session() as session:
            try:
                query = select(Task).where(Task.id == task_id).where(Task.user_id == user_id)
                task = session.exec(query).first()

                if task:
                    logger.info(f"Task {task_id} retrieved for user: {user_id}")
                else:
                    logger.info(f"Task {task_id} not found or not accessible by user: {user_id}")

                return task
            except SQLAlchemyError as e:
                logger.error(f"Failed to retrieve task {task_id} for user {user_id}: {str(e)}")
                raise

    @retry(
        retry=retry_if_exception_type((OperationalError, SQLAlchemyError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    def update_task(
        self,
        task_id: int,
        user_id: str,
        title: object = _UNSET,
        description: object = _UNSET,
        priority: object = _UNSET,
        due_date: object = _UNSET,
        category: object = _UNSET,
    ) -> Optional[Task]:
        """
        Update a task's title and/or description with transaction safety.

        Args:
            task_id: ID of the task to update
            user_id: ID of the user who owns the task
            title: New title (optional)
            description: New description (optional)

        Returns:
            Updated Task object if successful, None if task not found
        """
        with get_session() as session:
            try:
                task = session.get(Task, task_id)

                # Verify user owns the task
                if not task or task.user_id != user_id:
                    logger.warning(f"Attempt to update task {task_id} by unauthorized user: {user_id}")
                    return None

                # Update fields if provided
                if title is not _UNSET:
                    task.title = title
                if description is not _UNSET:
                    task.description = description
                if priority is not _UNSET:
                    task.priority = priority
                if due_date is not _UNSET:
                    task.due_date = due_date
                if category is not _UNSET:
                    task.category = category

                task.updated_at = datetime.utcnow()
                session.add(task)
                session.commit()
                session.refresh(task)

                logger.info(f"Task {task_id} updated successfully for user: {user_id}")
                return task
            except SQLAlchemyError as e:
                session.rollback()
                logger.error(f"Failed to update task {task_id} for user {user_id}: {str(e)}")
                raise

    @retry(
        retry=retry_if_exception_type((OperationalError, SQLAlchemyError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    def complete_task(self, task_id: int, user_id: str) -> Optional[Task]:
        """
        Mark a task as completed (idempotent operation) with transaction safety.

        Args:
            task_id: ID of the task to complete
            user_id: ID of the user who owns the task

        Returns:
            Updated Task object if successful, None if task not found
        """
        with get_session() as session:
            try:
                task = session.get(Task, task_id)

                # Verify user owns the task
                if not task or task.user_id != user_id:
                    logger.warning(f"Attempt to complete task {task_id} by unauthorized user: {user_id}")
                    return None

                # Toggle completion status
                task.completed = not task.completed
                task.updated_at = datetime.utcnow()
                session.add(task)
                session.commit()
                session.refresh(task)

                status = "completed" if task.completed else "pending"
                logger.info(f"Task {task_id} toggled to {status} for user: {user_id}")
                return task
            except SQLAlchemyError as e:
                session.rollback()
                logger.error(f"Failed to complete task {task_id} for user {user_id}: {str(e)}")
                raise

    @retry(
        retry=retry_if_exception_type((OperationalError, SQLAlchemyError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    def delete_task(self, task_id: int, user_id: str) -> bool:
        """
        Delete a task with transaction safety.

        Args:
            task_id: ID of the task to delete
            user_id: ID of the user who owns the task

        Returns:
            True if deletion was successful, False if task not found
        """
        with get_session() as session:
            try:
                task = session.get(Task, task_id)

                # Verify user owns the task
                if not task or task.user_id != user_id:
                    logger.warning(f"Attempt to delete task {task_id} by unauthorized user: {user_id}")
                    return False

                session.delete(task)
                session.commit()

                logger.info(f"Task {task_id} deleted successfully for user: {user_id}")
                return True
            except SQLAlchemyError as e:
                session.rollback()
                logger.error(f"Failed to delete task {task_id} for user {user_id}: {str(e)}")
                raise

    @retry(
        retry=retry_if_exception_type((OperationalError, SQLAlchemyError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    def task_exists(self, task_id: int) -> bool:
        """
        Check if a task exists regardless of ownership with connection resilience.

        Args:
            task_id: ID of the task to check

        Returns:
            True if task exists, False otherwise
        """
        with get_session() as session:
            try:
                task = session.get(Task, task_id)
                exists = task is not None
                logger.info(f"Task {task_id} existence check: {exists}")
                return exists
            except SQLAlchemyError as e:
                logger.error(f"Failed to check existence of task {task_id}: {str(e)}")
                raise

    @retry(
        retry=retry_if_exception_type((OperationalError, SQLAlchemyError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    def bulk_update_tasks(self, task_ids: List[int], user_id: str, **updates) -> int:
        """
        Update multiple tasks for a user in a single transaction.

        Args:
            task_ids: List of task IDs to update
            user_id: ID of the user who owns the tasks
            **updates: Fields to update

        Returns:
            Number of tasks successfully updated
        """
        with get_session() as session:
            try:
                # Get tasks that belong to the user
                query = select(Task).where(
                    Task.id.in_(task_ids),
                    Task.user_id == user_id
                )
                tasks = session.exec(query).all()

                if not tasks:
                    return 0

                # Update fields for each task
                updated_count = 0
                for task in tasks:
                    for field, value in updates.items():
                        if hasattr(task, field):
                            setattr(task, field, value)
                    task.updated_at = datetime.utcnow()
                    session.add(task)
                    updated_count += 1

                session.commit()
                logger.info(f"Bulk updated {updated_count} tasks for user: {user_id}")
                return updated_count
            except SQLAlchemyError as e:
                session.rollback()
                logger.error(f"Failed to bulk update tasks for user {user_id}: {str(e)}")
                raise

    @retry(
        retry=retry_if_exception_type((OperationalError, SQLAlchemyError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    def get_task_stats(self, user_id: str) -> dict:
        """
        Get statistics for user's tasks with connection resilience.

        Args:
            user_id: ID of the user to get stats for

        Returns:
            Dictionary with task statistics
        """
        with get_session() as session:
            try:
                # Total tasks
                total_query = select(Task).where(Task.user_id == user_id)
                total_tasks = len(session.exec(total_query).all())

                # Completed tasks
                completed_query = select(Task).where(
                    Task.user_id == user_id,
                    Task.completed == True
                )
                completed_tasks = len(session.exec(completed_query).all())

                # Pending tasks
                pending_tasks = total_tasks - completed_tasks

                stats = {
                    "total": total_tasks,
                    "completed": completed_tasks,
                    "pending": pending_tasks,
                    "completion_rate": total_tasks > 0 and (completed_tasks / total_tasks) * 100 or 0
                }

                logger.info(f"Retrieved task stats for user: {user_id}")
                return stats
            except SQLAlchemyError as e:
                logger.error(f"Failed to get task stats for user {user_id}: {str(e)}")
                raise


# Global instance of TaskService
task_service = TaskService()
