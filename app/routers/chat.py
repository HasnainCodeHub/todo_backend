"""Chat API router for AI chatbot integration.

This router provides endpoints for:
- POST /api/chat - Send a message to the AI assistant
- GET /api/conversations - List user's conversations
- GET /api/conversations/{id} - Get conversation with messages
- DELETE /api/conversations/{id} - Delete a conversation
"""

import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status

from ..dependencies.auth import AuthenticatedUser, get_current_user
from ..schemas.chat import (
    ChatRequest,
    ChatResponse,
    ConversationResponse,
    ConversationWithMessagesResponse,
    MessageResponse,
)
from ..services.chat_service import process_chat
from ..crud.conversation import (
    list_conversations,
    get_conversation,
    get_messages,
    delete_conversation,
    count_messages,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    authorization: Annotated[str | None, Header()] = None,
) -> ChatResponse:
    """Send a message to the AI assistant.

    The AI agent interprets natural language messages and invokes MCP tools
    to perform task operations (create, list, update, complete, delete).

    Args:
        request: ChatRequest with message and optional conversation_id
        current_user: Authenticated user from JWT
        authorization: Raw authorization header for MCP tool calls

    Returns:
        ChatResponse with conversation_id, AI response, and metadata
    """
    logger.info(f"Chat request from user {current_user.user_id}")

    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required"
        )

    # Validate conversation_id format if provided
    if request.conversation_id:
        # Basic UUID format check (not strict validation)
        if len(request.conversation_id) != 36 or request.conversation_id.count("-") != 4:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid conversation_id format"
            )

    response = await process_chat(
        user_id=current_user.user_id,
        message=request.message,
        conversation_id=request.conversation_id,
        authorization=authorization
    )

    return response


@router.get("/conversations", response_model=list[ConversationResponse])
async def list_user_conversations(
    current_user: AuthenticatedUser = Depends(get_current_user),
    limit: int = 20,
    offset: int = 0,
) -> list[ConversationResponse]:
    """List all conversations for the authenticated user.

    Args:
        current_user: Authenticated user from JWT
        limit: Maximum number of conversations to return (default 20, max 100)
        offset: Number of conversations to skip for pagination

    Returns:
        List of conversation summaries ordered by most recent
    """
    # Validate limit
    if limit > 100:
        limit = 100
    if limit < 1:
        limit = 1

    conversations = list_conversations(
        user_id=current_user.user_id,
        limit=limit,
        offset=offset
    )

    return [
        ConversationResponse(
            id=conv.id,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            message_count=count_messages(conv.id)
        )
        for conv in conversations
    ]


@router.get("/conversations/{conversation_id}", response_model=ConversationWithMessagesResponse)
async def get_conversation_detail(
    conversation_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
    limit: int = 20,
) -> ConversationWithMessagesResponse:
    """Get a specific conversation with its message history.

    Args:
        conversation_id: The ID of the conversation to retrieve
        current_user: Authenticated user from JWT
        limit: Maximum number of messages to return (default 20, max 100)

    Returns:
        Conversation details with message history

    Raises:
        HTTPException 404: If conversation not found or not owned by user
    """
    # Validate limit
    if limit > 100:
        limit = 100
    if limit < 1:
        limit = 1

    conversation = get_conversation(conversation_id, current_user.user_id)
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )

    messages = get_messages(conversation_id, limit=limit)

    return ConversationWithMessagesResponse(
        id=conversation.id,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=[
            MessageResponse(
                id=msg.id,
                role=msg.role,
                content=msg.content,
                created_at=msg.created_at
            )
            for msg in messages
        ]
    )


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_conversation(
    conversation_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> None:
    """Delete a conversation and all its messages.

    Args:
        conversation_id: The ID of the conversation to delete
        current_user: Authenticated user from JWT

    Raises:
        HTTPException 404: If conversation not found or not owned by user
    """
    deleted = delete_conversation(conversation_id, current_user.user_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
