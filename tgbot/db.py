"""
Database models and session management.
"""

import uuid
from datetime import datetime
from sqlalchemy import create_engine, Column, BigInteger, String, DateTime, Integer, ForeignKey, Index, Text
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from contextlib import contextmanager

import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./tgbot.db")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "hermes4:70b")
MAX_MESSAGES_PER_USER = 1024

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def generate_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    chat_id = Column(BigInteger, primary_key=True)
    api_key = Column(String, nullable=True)
    model = Column(String, default=DEFAULT_MODEL)
    current_context_id = Column(String, default=generate_uuid)
    webhook_secret = Column(String, unique=True, default=generate_uuid)
    free = Column(Integer, default=0)  # 0 = not free, 1 = free account used
    created_at = Column(DateTime, default=datetime.utcnow)

    messages = relationship("Message", back_populates="user", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(BigInteger, ForeignKey("users.chat_id"), nullable=False)
    message_id = Column(BigInteger, nullable=True)  # Telegram message ID (nullable for system messages)
    context_id = Column(String, nullable=False)
    role = Column(String, nullable=False)  # user, assistant, context_marker
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="messages")

    __table_args__ = (
        Index("ix_messages_chat_context", "chat_id", "context_id"),
        Index("ix_messages_chat_created", "chat_id", "created_at"),
    )


@contextmanager
def get_session():
    """Context manager for database sessions."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_user(chat_id: int) -> User | None:
    """Get user by chat_id."""
    with get_session() as session:
        user = session.query(User).filter(User.chat_id == chat_id).first()
        if user:
            # Detach from session
            session.expunge(user)
        return user


def get_or_create_user(chat_id: int) -> User:
    """Get or create user by chat_id."""
    with get_session() as session:
        user = session.query(User).filter(User.chat_id == chat_id).first()
        if not user:
            user = User(chat_id=chat_id, model=DEFAULT_MODEL)
            session.add(user)
            session.commit()
            session.refresh(user)  # Load all attributes including defaults
        session.expunge(user)
        return user


def set_api_key(chat_id: int, api_key: str) -> None:
    """Set user's API key."""
    with get_session() as session:
        user = session.query(User).filter(User.chat_id == chat_id).first()
        if user:
            user.api_key = api_key
        else:
            user = User(chat_id=chat_id, api_key=api_key, model=DEFAULT_MODEL)
            session.add(user)


def set_model(chat_id: int, model: str) -> None:
    """Set user's model preference."""
    with get_session() as session:
        user = session.query(User).filter(User.chat_id == chat_id).first()
        if user:
            user.model = model


def clear_api_key(chat_id: int) -> None:
    """Clear user's API key."""
    with get_session() as session:
        user = session.query(User).filter(User.chat_id == chat_id).first()
        if user:
            user.api_key = None


def set_free_account(chat_id: int, jwt_token: str) -> None:
    """Set user's free account JWT token and mark as free account used."""
    with get_session() as session:
        user = session.query(User).filter(User.chat_id == chat_id).first()
        if user:
            user.api_key = jwt_token
            user.free = 1


def get_user_by_webhook_secret(webhook_secret: str) -> User | None:
    """Get user by webhook secret."""
    with get_session() as session:
        user = session.query(User).filter(User.webhook_secret == webhook_secret).first()
        if user:
            session.expunge(user)
        return user


def new_context(chat_id: int) -> str:
    """Create a new context for user, returns the new context_id."""
    new_context_id = generate_uuid()
    with get_session() as session:
        user = session.query(User).filter(User.chat_id == chat_id).first()
        if user:
            user.current_context_id = new_context_id
    return new_context_id


def set_context(chat_id: int, context_id: str) -> None:
    """Set user's current context to an existing context_id."""
    with get_session() as session:
        user = session.query(User).filter(User.chat_id == chat_id).first()
        if user:
            user.current_context_id = context_id


def add_message(chat_id: int, context_id: str, role: str, content: str, message_id: int | None = None) -> Message:
    """Add a message to the database, rotating if over limit (per user, not per context)."""
    with get_session() as session:
        # Count ALL messages for this user
        count = session.query(Message).filter(
            Message.chat_id == chat_id
        ).count()

        # Rotate: delete oldest if at limit
        if count >= MAX_MESSAGES_PER_USER:
            oldest = session.query(Message).filter(
                Message.chat_id == chat_id
            ).order_by(Message.created_at.asc()).first()
            if oldest:
                session.delete(oldest)

        # Add new message
        msg = Message(
            chat_id=chat_id,
            message_id=message_id,
            context_id=context_id,
            role=role,
            content=content,
        )
        session.add(msg)
        session.commit()
        session.expunge(msg)
        return msg


def get_context_messages(chat_id: int, context_id: str) -> list[dict]:
    """Get all messages for a context, ordered by creation time."""
    with get_session() as session:
        messages = session.query(Message).filter(
            Message.chat_id == chat_id,
            Message.context_id == context_id,
            Message.role != "context_marker"  # Exclude markers from LLM context
        ).order_by(Message.created_at.asc()).all()

        return [{"role": m.role, "content": m.content} for m in messages]


def update_message_by_telegram_id(chat_id: int, message_id: int, content: str) -> bool:
    """Update a message by its Telegram message_id. Returns True if found and updated."""
    with get_session() as session:
        msg = session.query(Message).filter(
            Message.chat_id == chat_id,
            Message.message_id == message_id
        ).first()
        if msg:
            msg.content = content
            return True
        return False


def get_message_by_telegram_id(chat_id: int, message_id: int) -> Message | None:
    """Get a message by its Telegram message_id."""
    with get_session() as session:
        msg = session.query(Message).filter(
            Message.chat_id == chat_id,
            Message.message_id == message_id
        ).first()
        if msg:
            session.expunge(msg)
        return msg


def get_last_user_message(chat_id: int) -> str | None:
    """Get the last user message content (for language detection in webhooks)."""
    with get_session() as session:
        msg = session.query(Message).filter(
            Message.chat_id == chat_id,
            Message.role == "user"
        ).order_by(Message.created_at.desc()).first()
        return msg.content if msg else None


def resume_context(chat_id: int, marker_context_id: str) -> str | None:
    """
    Resume a previous context by merging messages.

    When user clicks "Resume this context" on a #NewContext marker:
    1. Find the context_id from messages BEFORE the marker (previous context)
    2. Update all messages with marker_context_id to use the previous context_id
    3. Delete the marker message from DB
    4. Return the previous context_id (caller should also delete marker from Telegram)

    Returns the previous context_id, or None if not found.
    """
    with get_session() as session:
        # Find the marker message
        marker = session.query(Message).filter(
            Message.chat_id == chat_id,
            Message.context_id == marker_context_id,
            Message.role == "context_marker"
        ).first()

        if not marker:
            return None

        marker_created_at = marker.created_at

        # Find the most recent message BEFORE the marker (different context_id)
        prev_message = session.query(Message).filter(
            Message.chat_id == chat_id,
            Message.created_at < marker_created_at,
            Message.context_id != marker_context_id
        ).order_by(Message.created_at.desc()).first()

        if not prev_message:
            # No previous context - this was the first context
            # Just delete the marker, keep current context_id
            session.delete(marker)
            return marker_context_id

        previous_context_id = prev_message.context_id

        # Update all messages with marker_context_id to use previous_context_id
        session.query(Message).filter(
            Message.chat_id == chat_id,
            Message.context_id == marker_context_id
        ).update({Message.context_id: previous_context_id})

        # The marker was already updated above, but we want to delete it
        # Re-fetch and delete
        marker = session.query(Message).filter(
            Message.chat_id == chat_id,
            Message.role == "context_marker",
            Message.created_at == marker_created_at
        ).first()
        if marker:
            session.delete(marker)

        return previous_context_id


def delete_message_by_telegram_id(chat_id: int, message_id: int) -> bool:
    """Delete a message by its Telegram message_id. Returns True if found and deleted."""
    with get_session() as session:
        msg = session.query(Message).filter(
            Message.chat_id == chat_id,
            Message.message_id == message_id
        ).first()
        if msg:
            session.delete(msg)
            return True
        return False


def get_marker_telegram_id(chat_id: int, context_id: str) -> int | None:
    """Get the Telegram message_id of the context marker for a given context."""
    with get_session() as session:
        marker = session.query(Message).filter(
            Message.chat_id == chat_id,
            Message.context_id == context_id,
            Message.role == "context_marker"
        ).first()
        return marker.message_id if marker else None
