from fastapi import APIRouter, Depends, status, HTTPException
from typing import List

from ..schemas import TaskCreate, TaskUpdate, TaskResponse
from ..dependencies import get_current_user, AuthenticatedUser
from ..crud import task as crud

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    payload: TaskCreate,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """Create a new task."""
    try:
        return crud.create_task(
            title=payload.title,
            description=payload.description,
            priority=payload.priority,
            due_date=payload.due_date,
            category=payload.category,
            user_id=current_user.user_id
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database error: {str(e)}"
        )


@router.get("", response_model=List[TaskResponse])
async def list_tasks(current_user: AuthenticatedUser = Depends(get_current_user)):
    """List all tasks for the current user."""
    try:
        return crud.get_tasks(user_id=current_user.user_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database error: {str(e)}"
        )


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: int, current_user: AuthenticatedUser = Depends(get_current_user)):
    """Get a specific task by ID."""
    try:
        task = crud.get_task(task_id=task_id, user_id=current_user.user_id)
        if not task:
            # Check if task exists for any user to determine 403 vs 404
            if crud.task_exists_any_user(task_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: task belongs to another user"
                )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )
        return task
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database error: {str(e)}"
        )


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    payload: TaskUpdate,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """Update a specific task."""
    try:
        update_data = payload.model_dump(exclude_unset=True)
        task = crud.update_task(
            task_id=task_id,
            user_id=current_user.user_id,
            **update_data
        )
        if not task:
            # Check if task exists for any user to determine 403 vs 404
            if crud.task_exists_any_user(task_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: task belongs to another user"
                )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )
        return task
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database error: {str(e)}"
        )


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: int, current_user: AuthenticatedUser = Depends(get_current_user)):
    """Delete a specific task."""
    try:
        success = crud.delete_task(task_id=task_id, user_id=current_user.user_id)
        if not success:
            # Check if task exists for any user to determine 403 vs 404
            if crud.task_exists_any_user(task_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: task belongs to another user"
                )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )
        return None
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database error: {str(e)}"
        )


@router.patch("/{task_id}/complete", response_model=TaskResponse)
async def toggle_task_complete(task_id: int, current_user: AuthenticatedUser = Depends(get_current_user)):
    """Toggle task completion status."""
    try:
        task = crud.toggle_complete(task_id=task_id, user_id=current_user.user_id)
        if not task:
            # Check if task exists for any user to determine 403 vs 404
            if crud.task_exists_any_user(task_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: task belongs to another user"
                )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )
        return task
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database error: {str(e)}"
        )
