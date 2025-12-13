"""
Database models and session management.
Supports both Telegram users (chat_id) and web users (user_id from JWT).
"""

import uuid
import os
from datetime import datetime
from sqlalchemy import create_engine, Column, BigInteger, String, DateTime, Integer, ForeignKey, Index, Text
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv()

# Build DATABASE_URL from individual components
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
DB_SSLMODE = os.getenv("DB_SSLMODE", "require")

if DB_HOST and DB_USER and DB_PASSWORD and DB_NAME:
    DATABASE_URL = f"postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT or '5432'}/{DB_NAME}?sslmode={DB_SSLMODE}"
    ENGINE_ARGS = {
        "pool_size": 10,
        "max_overflow": 20,
        "pool_timeout": 30,
        "pool_pre_ping": True,
    }
else:
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./bot.db")
    ENGINE_ARGS = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "minimax-m2")
MAX_MESSAGES_PER_USER = 2048

engine = create_engine(DATABASE_URL, connect_args=ENGINE_ARGS if DATABASE_URL.startswith("sqlite") else {}, **({} if DATABASE_URL.startswith("sqlite") else ENGINE_ARGS))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def generate_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    """
    User model - supports both Telegram and web users.

    - user_id: Primary identifier (UUID for web users, 'tg_{chat_id}' for Telegram)
    - chat_id: Telegram chat ID (nullable, only for Telegram users)
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, unique=True, nullable=False, index=True)  # Primary identifier
    chat_id = Column(BigInteger, nullable=True, unique=True, index=True)  # Telegram only
    api_key = Column(String, nullable=True)
    model = Column(String, default=DEFAULT_MODEL)
    current_thread_id = Column(String, ForeignKey("threads.id"), nullable=True)
    webhook_secret = Column(String, unique=True, default=generate_uuid)
    free = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    threads = relationship("Thread", back_populates="user", foreign_keys="Thread.user_id")
    current_thread = relationship("Thread", foreign_keys=[current_thread_id], post_update=True)


class Thread(Base):
    __tablename__ = "threads"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False, index=True)
    chat_id = Column(BigInteger, nullable=True)  # Legacy, kept for migration
    title = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="threads", foreign_keys=[user_id])
    messages = relationship("Message", back_populates="thread", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_threads_updated_at", "updated_at"),
    )


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False, index=True)
    chat_id = Column(BigInteger, nullable=True)  # Legacy, kept for migration
    thread_id = Column(String, ForeignKey("threads.id"), nullable=False)
    telegram_message_id = Column(BigInteger, nullable=True)  # Telegram-specific
    role = Column(String, nullable=False)  # user, assistant
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    thread = relationship("Thread", back_populates="messages")

    __table_args__ = (
        Index("ix_messages_thread_id", "thread_id"),
        Index("ix_messages_user_created", "user_id", "created_at"),
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


# =============================================================================
# User functions - by user_id (primary)
# =============================================================================

def get_user_by_user_id(user_id: str) -> User | None:
    """Get user by user_id (primary identifier)."""
    with get_session() as session:
        user = session.query(User).filter(User.user_id == user_id).first()
        if user:
            session.expunge(user)
        return user


def create_user(user_id: str, chat_id: int | None = None, api_key: str | None = None) -> User:
    """Create a new user."""
    with get_session() as session:
        user = User(
            user_id=user_id,
            chat_id=chat_id,
            api_key=api_key,
            model=DEFAULT_MODEL,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        session.expunge(user)
        return user


def get_or_create_user_by_user_id(user_id: str, chat_id: int | None = None) -> User:
    """Get or create user by user_id."""
    user = get_user_by_user_id(user_id)
    if not user:
        user = create_user(user_id, chat_id)
    return user


def set_user_api_key(user_id: str, api_key: str) -> None:
    """Set user's API key."""
    with get_session() as session:
        user = session.query(User).filter(User.user_id == user_id).first()
        if user:
            user.api_key = api_key


def set_user_model(user_id: str, model: str) -> None:
    """Set user's model preference."""
    with get_session() as session:
        user = session.query(User).filter(User.user_id == user_id).first()
        if user:
            user.model = model


def clear_user_api_key(user_id: str) -> None:
    """Clear user's API key."""
    with get_session() as session:
        user = session.query(User).filter(User.user_id == user_id).first()
        if user:
            user.api_key = None


def set_free_account_by_user_id(user_id: str, jwt_token: str) -> None:
    """Set user's free account JWT token by user_id."""
    with get_session() as session:
        user = session.query(User).filter(User.user_id == user_id).first()
        if user:
            user.api_key = jwt_token
            user.free = 1


def set_free_account(chat_id: int, jwt_token: str) -> None:
    """Set user's free account JWT token by chat_id (legacy Telegram)."""
    with get_session() as session:
        user = session.query(User).filter(User.chat_id == chat_id).first()
        if user:
            user.api_key = jwt_token
            user.free = 1


# =============================================================================
# User functions - by chat_id (Telegram compatibility)
# =============================================================================

def get_user(chat_id: int) -> User | None:
    """Get user by Telegram chat_id (legacy compatibility)."""
    with get_session() as session:
        user = session.query(User).filter(User.chat_id == chat_id).first()
        if user:
            session.expunge(user)
        return user


def get_or_create_user(chat_id: int) -> User:
    """Get or create user by Telegram chat_id."""
    user = get_user(chat_id)
    if not user:
        user_id = f"tg_{chat_id}"
        user = create_user(user_id, chat_id)
    return user


def set_api_key(chat_id: int, api_key: str) -> None:
    """Set user's API key by chat_id (legacy)."""
    with get_session() as session:
        user = session.query(User).filter(User.chat_id == chat_id).first()
        if user:
            user.api_key = api_key
        else:
            user_id = f"tg_{chat_id}"
            user = User(user_id=user_id, chat_id=chat_id, api_key=api_key, model=DEFAULT_MODEL)
            session.add(user)


def set_model(chat_id: int, model: str) -> None:
    """Set user's model preference by chat_id (legacy)."""
    with get_session() as session:
        user = session.query(User).filter(User.chat_id == chat_id).first()
        if user:
            user.model = model


def clear_api_key(chat_id: int) -> None:
    """Clear user's API key by chat_id (legacy)."""
    with get_session() as session:
        user = session.query(User).filter(User.chat_id == chat_id).first()
        if user:
            user.api_key = None


def get_user_by_webhook_secret(webhook_secret: str) -> User | None:
    """Get user by webhook secret."""
    with get_session() as session:
        user = session.query(User).filter(User.webhook_secret == webhook_secret).first()
        if user:
            session.expunge(user)
        return user


# =============================================================================
# Thread functions - by user_id (primary)
# =============================================================================

def create_thread_for_user(user_id: str, title: str | None = None) -> Thread:
    """Create a new thread for user."""
    with get_session() as session:
        user = session.query(User).filter(User.user_id == user_id).first()
        if not user:
            raise ValueError(f"User not found: {user_id}")

        thread = Thread(user_id=user_id, chat_id=user.chat_id, title=title)
        session.add(thread)
        session.commit()
        session.refresh(thread)

        # Set as current thread
        user.current_thread_id = thread.id
        session.commit()

        session.expunge(thread)
        return thread


def get_user_threads_by_user_id(user_id: str, limit: int = 20) -> list[Thread]:
    """Get user's threads by user_id, ordered by most recent activity."""
    with get_session() as session:
        threads = session.query(Thread).filter(
            Thread.user_id == user_id
        ).order_by(Thread.updated_at.desc()).limit(limit).all()

        for t in threads:
            session.expunge(t)
        return threads


def get_or_create_current_thread_for_user(user_id: str) -> Thread:
    """Get user's current thread by user_id, creating one if needed."""
    with get_session() as session:
        user = session.query(User).filter(User.user_id == user_id).first()
        if not user:
            raise ValueError(f"User not found: {user_id}")

        if user.current_thread_id:
            thread = session.query(Thread).filter(Thread.id == user.current_thread_id).first()
            if thread:
                session.expunge(thread)
                return thread

        # Create new thread
        thread = Thread(user_id=user_id, chat_id=user.chat_id)
        session.add(thread)
        session.commit()
        session.refresh(thread)

        user.current_thread_id = thread.id
        session.commit()

        session.expunge(thread)
        return thread


# =============================================================================
# Thread functions - by chat_id (Telegram compatibility)
# =============================================================================

def create_thread(chat_id: int, title: str | None = None) -> Thread:
    """Create a new thread for user by chat_id (legacy)."""
    with get_session() as session:
        user = session.query(User).filter(User.chat_id == chat_id).first()
        if not user:
            raise ValueError(f"User not found for chat_id: {chat_id}")

        thread = Thread(user_id=user.user_id, chat_id=chat_id, title=title)
        session.add(thread)
        session.commit()
        session.refresh(thread)

        user.current_thread_id = thread.id
        session.commit()

        session.expunge(thread)
        return thread


def get_or_create_current_thread(chat_id: int) -> Thread:
    """Get user's current thread by chat_id, creating one if needed."""
    with get_session() as session:
        user = session.query(User).filter(User.chat_id == chat_id).first()
        if not user:
            # Create user first
            user_id = f"tg_{chat_id}"
            user = User(user_id=user_id, chat_id=chat_id, model=DEFAULT_MODEL)
            session.add(user)
            session.commit()
            session.refresh(user)

        if user.current_thread_id:
            thread = session.query(Thread).filter(Thread.id == user.current_thread_id).first()
            if thread:
                session.expunge(thread)
                return thread

        # Create new thread
        thread = Thread(user_id=user.user_id, chat_id=chat_id)
        session.add(thread)
        session.commit()
        session.refresh(thread)

        user.current_thread_id = thread.id
        session.commit()

        session.expunge(thread)
        return thread


def new_thread(chat_id: int, title: str | None = None) -> Thread:
    """Create a new thread and set as current (legacy)."""
    return create_thread(chat_id, title)


def set_current_thread(chat_id: int, thread_id: str) -> bool:
    """Set user's current thread. Returns True if successful."""
    with get_session() as session:
        user = session.query(User).filter(User.chat_id == chat_id).first()
        if not user:
            return False

        # Verify thread exists and belongs to user
        thread = session.query(Thread).filter(
            Thread.id == thread_id,
            Thread.user_id == user.user_id
        ).first()
        if not thread:
            return False

        user.current_thread_id = thread_id
        return True


def get_user_threads(chat_id: int, limit: int = 20) -> list[Thread]:
    """Get user's threads by chat_id (legacy)."""
    with get_session() as session:
        user = session.query(User).filter(User.chat_id == chat_id).first()
        if not user:
            return []

        threads = session.query(Thread).filter(
            Thread.user_id == user.user_id
        ).order_by(Thread.updated_at.desc()).limit(limit).all()

        for t in threads:
            session.expunge(t)
        return threads


def get_thread(thread_id: str) -> Thread | None:
    """Get thread by ID."""
    with get_session() as session:
        thread = session.query(Thread).filter(Thread.id == thread_id).first()
        if thread:
            session.expunge(thread)
        return thread


def update_thread_title(thread_id: str, title: str) -> bool:
    """Update thread title."""
    with get_session() as session:
        thread = session.query(Thread).filter(Thread.id == thread_id).first()
        if thread:
            thread.title = title
            return True
        return False


def delete_thread(thread_id: str, chat_id: int) -> bool:
    """Delete a thread by chat_id (legacy)."""
    with get_session() as session:
        user = session.query(User).filter(User.chat_id == chat_id).first()
        if not user:
            return False

        thread = session.query(Thread).filter(
            Thread.id == thread_id,
            Thread.user_id == user.user_id
        ).first()
        if thread:
            if user.current_thread_id == thread_id:
                user.current_thread_id = None
            session.delete(thread)
            return True
        return False


def delete_thread_by_user_id(thread_id: str, user_id: str) -> bool:
    """Delete a thread by user_id."""
    with get_session() as session:
        thread = session.query(Thread).filter(
            Thread.id == thread_id,
            Thread.user_id == user_id
        ).first()
        if thread:
            user = session.query(User).filter(User.user_id == user_id).first()
            if user and user.current_thread_id == thread_id:
                user.current_thread_id = None
            session.delete(thread)
            return True
        return False


# =============================================================================
# Message functions
# =============================================================================

def add_message(
    user_id: str,
    thread_id: str,
    role: str,
    content: str,
    telegram_message_id: int | None = None,
    chat_id: int | None = None,
) -> Message:
    """Add a message to a thread, rotating if over limit per user."""
    with get_session() as session:
        # Update thread's updated_at
        thread = session.query(Thread).filter(Thread.id == thread_id).first()
        if thread:
            thread.updated_at = datetime.utcnow()
            # Auto-generate title from first user message
            if not thread.title and role == "user":
                thread.title = content[:50] + ("..." if len(content) > 50 else "")

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
            thread_id=thread_id,
            telegram_message_id=telegram_message_id,
            role=role,
            content=content,
        )
        session.add(msg)
        session.commit()
        session.refresh(msg)
        session.expunge(msg)
        return msg


def get_thread_messages(thread_id: str) -> list[dict]:
    """Get all messages for a thread, ordered by creation time."""
    with get_session() as session:
        messages = session.query(Message).filter(
            Message.thread_id == thread_id
        ).order_by(Message.created_at.asc()).all()

        return [{"role": m.role, "content": m.content} for m in messages]


def truncate_thread_at_message(thread_id: str, message_id: int, new_content: str) -> bool:
    """
    Truncate thread at a message and update its content.
    Deletes all messages after the specified message.
    """
    with get_session() as session:
        # Get the message
        msg = session.query(Message).filter(
            Message.id == message_id,
            Message.thread_id == thread_id
        ).first()
        if not msg:
            return False

        # Delete all messages after this one
        session.query(Message).filter(
            Message.thread_id == thread_id,
            Message.created_at > msg.created_at
        ).delete()

        # Update the message content
        msg.content = new_content

        # Update thread timestamp
        thread = session.query(Thread).filter(Thread.id == thread_id).first()
        if thread:
            thread.updated_at = datetime.utcnow()

        return True


def update_message_by_telegram_id(chat_id: int, message_id: int, content: str) -> bool:
    """Update a message by its Telegram message_id (legacy)."""
    with get_session() as session:
        msg = session.query(Message).filter(
            Message.chat_id == chat_id,
            Message.telegram_message_id == message_id
        ).first()
        if msg:
            msg.content = content
            return True
        return False


def get_message_by_telegram_id(chat_id: int, message_id: int) -> Message | None:
    """Get a message by its Telegram message_id (legacy)."""
    with get_session() as session:
        msg = session.query(Message).filter(
            Message.chat_id == chat_id,
            Message.telegram_message_id == message_id
        ).first()
        if msg:
            session.expunge(msg)
        return msg


def get_last_user_message(chat_id: int) -> str | None:
    """Get the last user message content by chat_id (legacy)."""
    with get_session() as session:
        user = session.query(User).filter(User.chat_id == chat_id).first()
        if not user:
            return None

        msg = session.query(Message).filter(
            Message.user_id == user.user_id,
            Message.role == "user"
        ).order_by(Message.created_at.desc()).first()
        return msg.content if msg else None


def delete_message_by_telegram_id(chat_id: int, message_id: int) -> bool:
    """Delete a message by its Telegram message_id (legacy)."""
    with get_session() as session:
        msg = session.query(Message).filter(
            Message.chat_id == chat_id,
            Message.telegram_message_id == message_id
        ).first()
        if msg:
            session.delete(msg)
            return True
        return False


def get_user_webhook_secret(user_id: str) -> str | None:
    """Get user's webhook secret."""
    with get_session() as session:
        user = session.query(User).filter(User.user_id == user_id).first()
        return user.webhook_secret if user else None


# =============================================================================
# Render functions - moved to renders/ module
# =============================================================================
# Import from renders module:
#   from renders import (
#       create_render, get_render_by_render_id, update_render_status,
#       add_render_notification, get_unread_render_notifications,
#       mark_render_notifications_read,
#   )
