"""Conversation and Message models for AI chatbot persistence."""

from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field
import uuid


class Conversation(SQLModel, table=True):
    """A chat session between a user and the AI agent.

    Attributes:
        id: Unique conversation identifier (UUID)
        user_id: Owner of the conversation (from JWT)
        created_at: When conversation started
        updated_at: Last activity (for 30-day retention policy)
    """

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        primary_key=True
    )
    user_id: str = Field(index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Message(SQLModel, table=True):
    """A single message in a conversation.

    Attributes:
        id: Unique message identifier (auto-increment)
        conversation_id: Parent conversation (foreign key)
        role: "user" or "assistant"
        content: Message text
        created_at: When message was created
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    conversation_id: str = Field(
        foreign_key="conversation.id",
        index=True
    )
    role: str = Field(max_length=20)  # "user" or "assistant"
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
