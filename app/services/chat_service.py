"""Chat service for processing AI chatbot requests.

This service orchestrates conversation management and agent execution,
maintaining stateless request handling with database-backed persistence.
"""

import logging
from datetime import datetime
from typing import Optional

from ..agents.chat_orchestrator import run_agent
from ..crud.conversation import (
    get_or_create_conversation,
    add_message,
    get_messages,
    update_conversation_timestamp,
)
from ..schemas.chat import ChatResponse
from ..config import settings

logger = logging.getLogger(__name__)


async def process_chat(
    user_id: str,
    message: str,
    conversation_id: Optional[str],
    authorization: str
) -> ChatResponse:
    """Process a chat message and return AI response.

    This function:
    1. Gets or creates a conversation
    2. Loads conversation history from database
    3. Runs the AI agent with history and new message
    4. Saves both user message and assistant response
    5. Returns structured ChatResponse

    Args:
        user_id: The authenticated user's ID (from JWT)
        message: The user's natural language message
        conversation_id: Optional ID of existing conversation to continue
        authorization: JWT authorization header for MCP tool calls

    Returns:
        ChatResponse with conversation_id, message, and metadata

    Raises:
        RuntimeError: If agent execution fails
    """
    # Step 1: Get or create conversation
    conversation = get_or_create_conversation(user_id, conversation_id)
    logger.info(f"Processing chat for conversation {conversation.id}")

    # Step 2: Load conversation history
    history_messages = get_messages(
        conversation.id,
        limit=settings.chat_context_limit
    )

    # Convert to agent format
    history = [
        {"role": msg.role, "content": msg.content}
        for msg in history_messages
    ]

    # Step 3: Save user message BEFORE running agent
    # This ensures we don't lose the message if agent fails
    add_message(conversation.id, "user", message)

    try:
        # Step 4: Run the AI agent
        agent_response = await run_agent(
            user_message=message,
            history=history,
            authorization=authorization
        )

        # Step 5: Save assistant response (only on success)
        add_message(conversation.id, "assistant", agent_response)

        # Update conversation timestamp for retention tracking
        update_conversation_timestamp(conversation.id)

        # Step 6: Return structured response
        return ChatResponse(
            conversation_id=conversation.id,
            message=agent_response,
            actions_taken=None,
            created_at=datetime.utcnow()
        )

    except RuntimeError as e:
        # User-friendly error from agent — do NOT save to history
        # (saving error messages pollutes context and wastes tokens on retry)
        logger.warning(f"Agent runtime error: {e}")
        return ChatResponse(
            conversation_id=conversation.id,
            message=str(e),
            actions_taken=None,
            created_at=datetime.utcnow()
        )

    except Exception as e:
        logger.error(f"Chat processing error: {e}")
        error_str = str(e)

        # Detect rate limit / quota exhaustion (HTTP 429)
        if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str or "Too Many Requests" in error_str:
            error_message = (
                "The AI service is temporarily rate-limited. "
                "Please wait a moment and try again."
            )
        else:
            error_message = (
                "I'm sorry, I encountered an unexpected issue. "
                "Please try again in a moment."
            )

        # Do NOT save error messages to conversation history —
        # they pollute the context window and inflate token usage on every retry.
        return ChatResponse(
            conversation_id=conversation.id,
            message=error_message,
            actions_taken=None,
            created_at=datetime.utcnow()
        )
