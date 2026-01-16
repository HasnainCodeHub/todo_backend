"""Pydantic schemas for AI chatbot API."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator


class ChatRequest(BaseModel):
    """Incoming chat request from user.

    Attributes:
        message: User's natural language message (1-10,000 characters)
        conversation_id: ID of existing conversation to continue, or None to start new
    """

    message: str = Field(..., min_length=1, max_length=10000)
    conversation_id: Optional[str] = Field(
        None,
        description="ID of existing conversation to continue, or None to start new"
    )

    @field_validator("message")
    @classmethod
    def validate_message_not_whitespace(cls, v: str) -> str:
        """Validate that message is not only whitespace."""
        if not v.strip():
            raise ValueError("Message cannot be empty or whitespace only")
        return v


class ChatResponse(BaseModel):
    """Response from the AI agent.

    Attributes:
        conversation_id: ID of the conversation (new or existing)
        message: AI assistant's response
        actions_taken: List of MCP tool actions executed (optional)
        created_at: Timestamp of the response
    """

    conversation_id: str
    message: str
    actions_taken: Optional[list[str]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationResponse(BaseModel):
    """Summary of a conversation.

    Attributes:
        id: Conversation identifier
        created_at: When conversation started
        updated_at: Last activity timestamp
        message_count: Number of messages in conversation
    """

    id: str
    created_at: datetime
    updated_at: datetime
    message_count: int

    model_config = ConfigDict(from_attributes=True)


class MessageResponse(BaseModel):
    """A single message in response format.

    Attributes:
        id: Message identifier
        role: "user" or "assistant"
        content: Message text
        created_at: When message was created
    """

    id: int
    role: str
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationWithMessagesResponse(BaseModel):
    """Conversation with its message history.

    Attributes:
        id: Conversation identifier
        created_at: When conversation started
        updated_at: Last activity timestamp
        messages: List of messages in the conversation
    """

    id: str
    created_at: datetime
    updated_at: datetime
    messages: list[MessageResponse]

    model_config = ConfigDict(from_attributes=True)
