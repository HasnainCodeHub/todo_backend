"""Pydantic schemas for task validation in MCP Server."""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Literal


class TaskCreateRequest(BaseModel):
    """Schema for creating a new task."""

    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    priority: Literal["low", "medium", "high"] = "medium"
    due_date: Optional[datetime] = None
    category: Optional[str] = Field(None, max_length=50)


class TaskUpdateRequest(BaseModel):
    """Schema for updating an existing task."""

    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    priority: Optional[Literal["low", "medium", "high"]] = None
    due_date: Optional[datetime] = None
    category: Optional[str] = Field(None, max_length=50)
    completed: Optional[bool] = None


class TaskResponse(BaseModel):
    """Schema for task response."""

    id: int
    title: str
    description: Optional[str]
    priority: str
    due_date: Optional[datetime]
    category: Optional[str]
    completed: bool
    user_id: str
    created_at: datetime
    updated_at: datetime


class ListTasksRequest(BaseModel):
    """Schema for listing tasks request."""

    status: str = Field(default="all", pattern=r"^(all|pending|completed)$")


class ListTasksResponse(BaseModel):
    """Schema for listing tasks response."""

    tasks: List[TaskResponse]


class TaskIdRequest(BaseModel):
    """Schema for requests that require a task ID."""

    task_id: int


class SuccessResponse(BaseModel):
    """Schema for successful operation responses."""

    success: bool


class ErrorResponse(BaseModel):
    """Schema for error responses."""

    error: dict


class AddTaskResponse(BaseModel):
    """Schema for add_task response."""

    success: bool
    task: TaskResponse


class CompleteTaskResponse(BaseModel):
    """Schema for complete_task response."""

    success: bool
    task: TaskResponse


class DeleteTaskResponse(BaseModel):
    """Schema for delete_task response."""

    success: bool
    deleted_task_id: int
