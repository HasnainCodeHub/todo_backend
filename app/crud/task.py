# Task CRUD Operations
# Phase 2.1: Database Persistence Layer with Enhanced Transaction Handling
# Task ID: T015-T020 (US2: User Scoping, US3: Full CRUD)

from datetime import datetime, timezone
from typing import Optional, List

from sqlmodel import Session, select

from ..database import get_session
from ..models import Task
from ..schemas import TaskResponse
from ..services.task_service import task_service

_UNSET = object()


def _task_to_response(task: Task) -> TaskResponse:
    """
    Convert ORM Task to Pydantic TaskResponse.

    MUST be called while session is still active to avoid DetachedInstanceError.
    """
    return TaskResponse(
        id=task.id,
        user_id=task.user_id,
        title=task.title,
        description=task.description,
        priority=task.priority,
        due_date=task.due_date,
        category=task.category,
        completed=task.completed,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def create_task(
    title: str,
    user_id: str,
    description: Optional[str] = None,
    priority: str = "medium",
    due_date: Optional[datetime] = None,
    category: Optional[str] = None,
) -> TaskResponse:
    """
    Create a new task for a user with enhanced transaction handling and retry logic.

    Implements FR-004: create_task function that accepts task data and user_id,
    returns the created task with generated ID.

    Args:
        title: Task title (required)
        user_id: Owner identifier (required)
        description: Optional task description

    Returns:
        The created Task as TaskResponse (serialization-safe)
    """
    # Use the enhanced TaskService for transaction handling and retries
    task = task_service.create_task(
        title=title,
        description=description,
        user_id=user_id,
        priority=priority,
        due_date=due_date,
        category=category,
    )

    # Convert to Pydantic model
    return _task_to_response(task)


def task_exists_any_user(task_id: int) -> bool:
    """
    Check if a task exists, regardless of user ownership with connection resilience.

    Implements US3: Cross-User Access Prevention - supports 403 vs 404 distinction.

    Task ID: T017

    Args:
        task_id: The task ID to check

    Returns:
        True if task exists in database, False otherwise
    """
    return task_service.task_exists(task_id)


def get_task(task_id: int, user_id: Optional[str] = None) -> Optional[TaskResponse]:
    """
    Retrieve a single task by ID with enhanced transaction handling.

    Implements FR-005: get_task function that retrieves a single task by ID.

    Args:
        task_id: The task ID to retrieve
        user_id: Optional user_id for ownership filtering

    Returns:
        The TaskResponse if found, None otherwise
    """
    # If user_id is provided, use it for ownership verification
    if user_id is not None:
        task = task_service.get_task_by_id(task_id, user_id)
        if task is None:
            return None
        return _task_to_response(task)
    else:
        # Without user_id, we can't verify ownership, so return None
        # This maintains the security model
        return None


def get_tasks(user_id: Optional[str] = None) -> list[TaskResponse]:
    """
    Retrieve all tasks for a user with enhanced transaction handling and retry logic.

    Implements FR-006: get_tasks function that retrieves all tasks,
    optionally filtered by user_id.

    Args:
        user_id: Optional user_id to filter tasks by owner.
                 If None, returns empty list to maintain security model

    Returns:
        List of TaskResponse objects (serialization-safe)
    """
    # Only proceed if user_id is provided to maintain security model
    if user_id is None:
        return []

    # Use the enhanced TaskService for connection resilience
    tasks = task_service.get_tasks(user_id)

    # Convert all tasks to Pydantic models
    return [_task_to_response(task) for task in tasks]


def update_task(
    task_id: int,
    user_id: str,
    title: object = _UNSET,
    description: object = _UNSET,
    priority: object = _UNSET,
    due_date: object = _UNSET,
    category: object = _UNSET,
    completed: Optional[bool] = None,
) -> Optional[TaskResponse]:
    """
    Update an existing task's properties with enhanced transaction handling and retry logic.

    Implements FR-007: update_task function that modifies existing task properties.

    Args:
        task_id: The task ID to update
        user_id: Owner identifier (for ownership verification)
        title: New title (optional, only updates if provided)
        description: New description (optional, only updates if provided)
        completed: New completed status (optional, only updates if provided)

    Returns:
        The updated TaskResponse if found and owned by user, None otherwise
    """
    # If completed is provided, we need to handle this differently since the original
    # service method doesn't support updating completed status
    if completed is not None:
        # Use direct database operation for this case
        with get_session() as session:
            try:
                # Find task with user scoping
                statement = select(Task).where(
                    Task.id == task_id,
                    Task.user_id == user_id
                )
                task = session.exec(statement).first()

                if task is None:
                    return None

                # Update provided fields
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
                if completed is not None:
                    task.completed = completed

                # Update timestamp
                task.updated_at = datetime.now(timezone.utc)

                session.add(task)
                session.commit()
                session.refresh(task)
                # Convert to Pydantic model INSIDE session
                return _task_to_response(task)
            except Exception as e:
                session.rollback()
                raise
    else:
        # Use the enhanced TaskService for update without completed field
        updated_task = task_service.update_task(
            task_id=task_id,
            user_id=user_id,
            title=title,
            description=description,
            priority=priority,
            due_date=due_date,
            category=category,
        )

        if updated_task is None:
            return None

        return _task_to_response(updated_task)


def delete_task(task_id: int, user_id: str) -> bool:
    """
    Delete a task by ID with enhanced transaction handling and retry logic.

    Implements FR-008: delete_task function that removes a task by ID.

    Args:
        task_id: The task ID to delete
        user_id: Owner identifier (for ownership verification)

    Returns:
        True if task was deleted, False if not found or not owned by user
    """
    # Use the enhanced TaskService for transaction safety and retries
    return task_service.delete_task(task_id, user_id)


def toggle_complete(task_id: int, user_id: str) -> Optional[TaskResponse]:
    """
    Toggle the completed status of a task with enhanced transaction handling.

    Implements FR-009: toggle_complete function that flips the completed status.

    Args:
        task_id: The task ID to toggle
        user_id: Owner identifier (for ownership verification)

    Returns:
        The updated TaskResponse if found and owned by user, None otherwise
    """
    # Use the enhanced TaskService for transaction safety and retries
    updated_task = task_service.complete_task(task_id, user_id)

    if updated_task is None:
        return None

    return _task_to_response(updated_task)


def get_task_stats(user_id: str) -> dict:
    """
    Get statistics for user's tasks with connection resilience.

    Args:
        user_id: ID of the user to get stats for

    Returns:
        Dictionary with task statistics
    """
    return task_service.get_task_stats(user_id)


def bulk_update_tasks(task_ids: List[int], user_id: str, **updates) -> int:
    """
    Update multiple tasks for a user in a single transaction with retry logic.

    Args:
        task_ids: List of task IDs to update
        user_id: ID of the user who owns the tasks
        **updates: Fields to update

    Returns:
        Number of tasks successfully updated
    """
    return task_service.bulk_update_tasks(task_ids, user_id, **updates)
