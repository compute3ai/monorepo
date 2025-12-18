"""
Chat service - chat and message management functions.
"""

from datetime import datetime
from db.models import get_session, User, Chat, Message
from services.users import get_or_create_user

MAX_MESSAGES_PER_USER = 2048


# =============================================================================
# Chat functions
# =============================================================================


def create_chat(user_id: str, title: str | None = None) -> Chat:
    """Create a new chat for user and set as current."""
    # Auto-create user if not exists
    get_or_create_user(user_id)

    with get_session() as session:
        user = session.query(User).filter(User.user_id == user_id).first()

        chat = Chat(user_id=user_id, title=title)
        session.add(chat)
        session.commit()
        session.refresh(chat)

        user.current_chat_id = chat.id
        session.commit()

        # Refresh after second commit to load all attrs before detaching
        session.refresh(chat)
        session.expunge(chat)
        return chat


def get_chat(chat_id: str) -> Chat | None:
    """Get chat by ID."""
    with get_session() as session:
        chat = session.query(Chat).filter(Chat.id == chat_id).first()
        if chat:
            session.expunge(chat)
        return chat


def get_user_chats(user_id: str, limit: int = 20) -> list[Chat]:
    """Get user's chats, ordered by most recent activity."""
    with get_session() as session:
        chats = session.query(Chat).filter(
            Chat.user_id == user_id
        ).order_by(Chat.updated_at.desc()).limit(limit).all()

        for c in chats:
            session.expunge(c)
        return chats


def get_or_create_current_chat(user_id: str) -> Chat:
    """Get user's current chat, creating one if needed."""
    # Auto-create user if not exists
    get_or_create_user(user_id)

    with get_session() as session:
        user = session.query(User).filter(User.user_id == user_id).first()

        if user.current_chat_id:
            chat = session.query(Chat).filter(Chat.id == user.current_chat_id).first()
            if chat:
                session.expunge(chat)
                return chat

        # Create new chat
        chat = Chat(user_id=user_id)
        session.add(chat)
        session.commit()
        session.refresh(chat)

        user.current_chat_id = chat.id
        session.commit()

        # Refresh after second commit to load all attrs before detaching
        session.refresh(chat)
        session.expunge(chat)
        return chat


def set_current_chat(user_id: str, chat_id: str) -> bool:
    """Set user's current chat. Returns True if successful."""
    with get_session() as session:
        user = session.query(User).filter(User.user_id == user_id).first()
        if not user:
            return False

        chat = session.query(Chat).filter(
            Chat.id == chat_id,
            Chat.user_id == user_id
        ).first()
        if not chat:
            return False

        user.current_chat_id = chat_id
        return True


def update_chat_title(chat_id: str, title: str) -> bool:
    """Update chat title."""
    with get_session() as session:
        chat = session.query(Chat).filter(Chat.id == chat_id).first()
        if chat:
            chat.title = title
            return True
        return False


def delete_chat(chat_id: str, user_id: str) -> bool:
    """Delete a chat."""
    with get_session() as session:
        chat = session.query(Chat).filter(
            Chat.id == chat_id,
            Chat.user_id == user_id
        ).first()
        if chat:
            user = session.query(User).filter(User.user_id == user_id).first()
            if user and user.current_chat_id == chat_id:
                user.current_chat_id = None
            session.delete(chat)
            return True
        return False


def new_chat(user_id: str, title: str | None = None) -> Chat:
    """Create a new chat and set as current. Alias for create_chat."""
    return create_chat(user_id, title)


# =============================================================================
# Message functions
# =============================================================================


def add_message(
    user_id: str,
    chat_id: str,
    role: str,
    content: str,
    status: str = "complete",
    telegram_message_id: int | None = None,
    msg_type: str = "text",
    meta: dict | None = None,
) -> Message:
    """Add a message to a chat, rotating if over limit per user.

    Args:
        user_id: User identifier
        chat_id: Chat identifier
        role: Message role (user, assistant)
        content: Message content
        status: Message status (pending, streaming, complete, error)
        telegram_message_id: Optional Telegram message ID
        msg_type: Message type (text, selection, selection_response)
        meta: Optional metadata dict (e.g., selection options, tool calls)
    """
    with get_session() as session:
        # Update chat's updated_at
        chat = session.query(Chat).filter(Chat.id == chat_id).first()
        if chat:
            chat.updated_at = datetime.utcnow()
            # Auto-generate title from first user message
            if not chat.title and role == "user":
                chat.title = content[:50] + ("..." if len(content) > 50 else "")

        # Count ALL messages for this user
        count = session.query(Message).filter(Message.user_id == user_id).count()

        # Rotate: delete oldest if at limit
        if count >= MAX_MESSAGES_PER_USER:
            oldest = session.query(Message).filter(
                Message.user_id == user_id
            ).order_by(Message.created_at.asc()).first()
            if oldest:
                session.delete(oldest)

        # Add new message
        msg = Message(
            user_id=user_id,
            chat_id=chat_id,
            telegram_message_id=telegram_message_id,
            role=role,
            content=content,
            type=msg_type,
            meta=meta,
            status=status,
        )
        session.add(msg)
        session.commit()
        session.refresh(msg)
        session.expunge(msg)
        return msg


def create_assistant_message(user_id: str, chat_id: str) -> Message:
    """Create a pending assistant message for streaming."""
    return add_message(
        user_id=user_id,
        chat_id=chat_id,
        role="assistant",
        content="",
        status="pending",
    )


def update_message_content(message_id: int, content: str) -> bool:
    """Update message content (used during streaming)."""
    with get_session() as session:
        msg = session.query(Message).filter(Message.id == message_id).first()
        if msg:
            msg.content = content
            msg.updated_at = datetime.utcnow()
            return True
        return False


def update_message_status(
    message_id: int,
    status: str,
    content: str | None = None,
    error: str | None = None,
) -> bool:
    """Update message status (and optionally content/error)."""
    with get_session() as session:
        msg = session.query(Message).filter(Message.id == message_id).first()
        if msg:
            msg.status = status
            msg.updated_at = datetime.utcnow()
            if content is not None:
                msg.content = content
            if error is not None:
                msg.error = error
            return True
        return False


def get_messages(chat_id: str) -> list[dict]:
    """Get all messages for a chat, ordered by creation time."""
    with get_session() as session:
        messages = session.query(Message).filter(
            Message.chat_id == chat_id
        ).order_by(Message.created_at.asc()).all()

        return [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "type": m.type,
                "meta": m.meta,
                "status": m.status,
                "error": m.error,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ]


def get_message(message_id: int) -> Message | None:
    """Get message by ID."""
    with get_session() as session:
        msg = session.query(Message).filter(Message.id == message_id).first()
        if msg:
            session.expunge(msg)
        return msg


def truncate_at_message(chat_id: str, message_id: int, new_content: str) -> bool:
    """
    Truncate chat at a message and update its content.
    Deletes all messages after the specified message.
    """
    with get_session() as session:
        msg = session.query(Message).filter(
            Message.id == message_id,
            Message.chat_id == chat_id
        ).first()
        if not msg:
            return False

        # Delete all messages after this one
        session.query(Message).filter(
            Message.chat_id == chat_id,
            Message.created_at > msg.created_at
        ).delete()

        # Update the message content
        msg.content = new_content

        # Update chat timestamp
        chat = session.query(Chat).filter(Chat.id == chat_id).first()
        if chat:
            chat.updated_at = datetime.utcnow()

        return True


def get_message_by_telegram_id(telegram_id: int, telegram_message_id: int) -> Message | None:
    """Get a message by its Telegram message_id."""
    with get_session() as session:
        # Need to join with User to get telegram_id
        msg = session.query(Message).join(User, Message.user_id == User.user_id).filter(
            User.telegram_id == telegram_id,
            Message.telegram_message_id == telegram_message_id
        ).first()
        if msg:
            session.expunge(msg)
        return msg


def get_last_user_message(user_id: str) -> str | None:
    """Get the last user message content."""
    with get_session() as session:
        msg = session.query(Message).filter(
            Message.user_id == user_id,
            Message.role == "user"
        ).order_by(Message.created_at.desc()).first()
        return msg.content if msg else None


def create_selection_message(
    user_id: str,
    chat_id: str,
    content: str,
    options: list[dict],
    tool_call: dict | None = None,
) -> Message:
    """Create a selection message for user to choose from options.

    Args:
        user_id: User identifier
        chat_id: Chat identifier
        content: Display text explaining the selection
        options: List of options, each with 'id', 'label', and optional 'description'
        tool_call: Optional tool call data to execute after selection

    Example options:
        [
            {"id": "model_1", "label": "Fast Model", "description": "Quick but basic"},
            {"id": "model_2", "label": "Quality Model", "description": "Slower but better"},
            {"id": "cancel", "label": "Cancel"},
        ]
    """
    return add_message(
        user_id=user_id,
        chat_id=chat_id,
        role="assistant",
        content=content,
        status="complete",
        msg_type="selection",
        meta={
            "options": options,
            "tool_call": tool_call,
        },
    )


def add_selection_response(
    user_id: str,
    chat_id: str,
    selected_id: str,
    selected_label: str,
    tool_call: dict | None = None,
) -> Message:
    """Record user's selection response.

    Args:
        user_id: User identifier
        chat_id: Chat identifier
        selected_id: ID of the selected option
        selected_label: Display label of selected option (for content)
        tool_call: Tool call data from the original selection (to execute)
    """
    return add_message(
        user_id=user_id,
        chat_id=chat_id,
        role="user",
        content=selected_label,
        status="complete",
        msg_type="selection_response",
        meta={
            "selected": selected_id,
            "tool_call": tool_call,
        },
    )


def get_pending_selection(chat_id: str) -> Message | None:
    """Get the most recent unanswered selection message in a chat.

    Returns the selection message if the last assistant message is a selection
    that hasn't been responded to yet.
    """
    with get_session() as session:
        # Get the last two messages
        messages = session.query(Message).filter(
            Message.chat_id == chat_id
        ).order_by(Message.created_at.desc()).limit(2).all()

        if not messages:
            return None

        last_msg = messages[0]

        # If the last message is a selection from assistant, it's pending
        if last_msg.role == "assistant" and last_msg.type == "selection":
            session.expunge(last_msg)
            return last_msg

        return None


def delete_message_by_telegram_id(telegram_id: int, telegram_message_id: int) -> bool:
    """Delete a message by its Telegram message_id."""
    with get_session() as session:
        msg = session.query(Message).join(User, Message.user_id == User.user_id).filter(
            User.telegram_id == telegram_id,
            Message.telegram_message_id == telegram_message_id
        ).first()
        if msg:
            session.delete(msg)
            return True
        return False
