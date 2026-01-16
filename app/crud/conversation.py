"""CRUD operations for Conversation and Message models."""

from datetime import datetime, timedelta
from typing import Optional
from sqlmodel import select

from ..database import get_session
from ..models.conversation import Conversation, Message


def create_conversation(user_id: str) -> Conversation:
    """Create a new conversation for a user.

    Args:
        user_id: The ID of the user owning this conversation

    Returns:
        The created Conversation instance
    """
    with get_session() as session: # type: ignore
        conversation = Conversation(user_id=user_id)
        session.add(conversation)
        session.commit()
        session.refresh(conversation)
        return conversation


def get_conversation(conversation_id: str, user_id: str) -> Optional[Conversation]:
    """Get a conversation by ID, verifying ownership.

    Args:
        conversation_id: The ID of the conversation
        user_id: The ID of the user (for ownership verification)

    Returns:
        The Conversation if found and owned by user, None otherwise
    """
    with get_session() as session:
        return session.exec(
            select(Conversation)
            .where(Conversation.id == conversation_id)
            .where(Conversation.user_id == user_id)
        ).first()


def get_or_create_conversation(
    user_id: str,
    conversation_id: Optional[str] = None
) -> Conversation:
    """Get existing conversation or create new one.

    Args:
        user_id: The ID of the user
        conversation_id: Optional ID of existing conversation to retrieve

    Returns:
        Existing or newly created Conversation
    """
    if conversation_id:
        conversation = get_conversation(conversation_id, user_id)
        if conversation:
            return conversation
    return create_conversation(user_id)


def update_conversation_timestamp(conversation_id: str) -> None:
    """Update the updated_at timestamp for retention tracking.

    Args:
        conversation_id: The ID of the conversation to update
    """
    with get_session() as session:
        conversation = session.get(Conversation, conversation_id)
        if conversation:
            conversation.updated_at = datetime.utcnow()
            session.add(conversation)
            session.commit()


def list_conversations(user_id: str, limit: int = 20, offset: int = 0) -> list[Conversation]:
    """List all conversations for a user, ordered by most recent.

    Args:
        user_id: The ID of the user
        limit: Maximum number of conversations to return
        offset: Number of conversations to skip

    Returns:
        List of conversations ordered by updated_at descending
    """
    with get_session() as session:
        return list(session.exec(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
            .offset(offset)
            .limit(limit)
        ).all())


def delete_conversation(conversation_id: str, user_id: str) -> bool:
    """Delete a conversation and all its messages.

    Args:
        conversation_id: The ID of the conversation to delete
        user_id: The ID of the user (for ownership verification)

    Returns:
        True if deleted, False if not found or not owned
    """
    with get_session() as session:
        conversation = session.exec(
            select(Conversation)
            .where(Conversation.id == conversation_id)
            .where(Conversation.user_id == user_id)
        ).first()

        if not conversation:
            return False

        # Delete all messages first (cascade should handle this, but being explicit)
        messages = session.exec(
            select(Message).where(Message.conversation_id == conversation_id)
        ).all()
        for msg in messages:
            session.delete(msg)

        session.delete(conversation)
        session.commit()
        return True


def delete_old_conversations(days: int = 30) -> int:
    """Delete conversations older than specified days.

    Args:
        days: Number of days after which to delete conversations

    Returns:
        Count of conversations deleted
    """
    with get_session() as session:
        cutoff = datetime.utcnow() - timedelta(days=days)
        old_conversations = session.exec(
            select(Conversation)
            .where(Conversation.updated_at < cutoff)
        ).all()

        count = len(old_conversations)
        for conv in old_conversations:
            # Delete messages first
            messages = session.exec(
                select(Message).where(Message.conversation_id == conv.id)
            ).all()
            for msg in messages:
                session.delete(msg)
            session.delete(conv)

        session.commit()
        return count


def add_message(conversation_id: str, role: str, content: str) -> Message:
    """Add a message to a conversation.

    Args:
        conversation_id: The ID of the conversation
        role: "user" or "assistant"
        content: The message text

    Returns:
        The created Message instance
    """
    with get_session() as session:
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content
        )
        session.add(message)
        session.commit()
        session.refresh(message)

        # Update conversation timestamp
        conversation = session.get(Conversation, conversation_id)
        if conversation:
            conversation.updated_at = datetime.utcnow()
            session.add(conversation)
            session.commit()

        return message


def get_messages(conversation_id: str, limit: int = 20) -> list[Message]:
    """Get messages for a conversation, ordered chronologically.

    Args:
        conversation_id: The ID of the conversation
        limit: Maximum number of messages to return

    Returns:
        List of messages ordered by created_at ascending (chronological)
    """
    with get_session() as session:
        messages = session.exec(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        ).all()
        return list(reversed(messages))  # Chronological order


def count_messages(conversation_id: str) -> int:
    """Count messages in a conversation.

    Args:
        conversation_id: The ID of the conversation

    Returns:
        Number of messages in the conversation
    """
    with get_session() as session:
        messages = session.exec(
            select(Message)
            .where(Message.conversation_id == conversation_id)
        ).all()
        return len(list(messages))
