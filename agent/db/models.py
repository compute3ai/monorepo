"""
Database models - User, Chat, Message, Render.

Note: The database table for Chat is still named 'threads' for backwards compatibility.
A migration will rename it to 'chats'.
"""

import uuid
import os
from datetime import datetime
from sqlalchemy import (
    create_engine,
    Column,
    BigInteger,
    String,
    DateTime,
    Integer,
    ForeignKey,
    Index,
    Text,
    JSON,
)
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv()

# Database configuration
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
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./agent.db")
    ENGINE_ARGS = {}

# Create engine
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL, **ENGINE_ARGS)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def generate_uuid() -> str:
    return str(uuid.uuid4())


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
# Models
# =============================================================================


class User(Base):
    """
    User model - supports both Telegram and web users.

    - user_id: Primary identifier (UUID for web users, 'tg_{telegram_id}' for Telegram)
    - telegram_id: Telegram chat ID (nullable, only for Telegram users)
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, unique=True, nullable=False, index=True)
    telegram_id = Column(BigInteger, nullable=True, unique=True, index=True)  # Telegram chat ID
    api_key = Column(String, nullable=True)
    model = Column(String, default="minimax-m2")
    current_chat_id = Column(String, ForeignKey("chats.id"), nullable=True)
    webhook_secret = Column(String, unique=True, default=generate_uuid)
    free = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    chats = relationship("Chat", back_populates="user", foreign_keys="Chat.user_id")
    current_chat = relationship("Chat", foreign_keys=[current_chat_id], post_update=True)


class Chat(Base):
    """
    Chat (conversation) model.

    Note: Table name is 'chats' (migrated from 'threads').
    """
    __tablename__ = "chats"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False, index=True)
    title = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="chats", foreign_keys=[user_id])
    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_chats_updated_at", "updated_at"),
    )


class Message(Base):
    """
    Message model.

    Status flow for assistant messages:
    - pending: Message created, inference not started
    - streaming: Inference in progress, content being updated
    - complete: Inference finished successfully
    - error: Inference failed

    User messages are always 'complete'.

    Message types:
    - text: Regular text message (default)
    - selection: Assistant presenting options for user to choose
    - selection_response: User's selection from options

    The 'meta' field stores additional data based on type:
    - selection: {"options": [...], "tool_call": {...}}
    - selection_response: {"selected": "option_id", "tool_call": {...}}
    """
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False, index=True)
    chat_id = Column(String, ForeignKey("chats.id"), nullable=False)
    telegram_message_id = Column(BigInteger, nullable=True)  # Telegram-specific
    role = Column(String, nullable=False)  # user, assistant
    content = Column(Text, nullable=False, default="")
    type = Column(String, nullable=False, default="text")  # text, selection, selection_response
    meta = Column(JSON, nullable=True)  # Additional data based on message type
    status = Column(String, nullable=False, default="complete")  # pending, streaming, complete, error
    error = Column(Text, nullable=True)  # Error message if status is 'error'
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    chat = relationship("Chat", back_populates="messages")

    __table_args__ = (
        Index("ix_messages_chat_id", "chat_id"),
        Index("ix_messages_user_created", "user_id", "created_at"),
        Index("ix_messages_status", "status"),
    )


class Render(Base):
    """Track user renders and their chat associations."""
    __tablename__ = "renders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False, index=True)
    chat_id = Column(String, ForeignKey("chats.id"), nullable=False, index=True)
    render_id = Column(String, nullable=False, unique=True, index=True)
    prompt = Column(Text, nullable=True)
    template = Column(String, nullable=True)
    status = Column(String, nullable=False, default="pending")
    result_url = Column(String, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_renders_user_status", "user_id", "status"),
    )


class RenderNotification(Base):
    """Store render completion notifications for web clients."""
    __tablename__ = "render_notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False, index=True)
    render_id = Column(String, nullable=False)
    status = Column(String, nullable=False)
    result_url = Column(String, nullable=True)
    error = Column(Text, nullable=True)
    read = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_render_notifications_user_unread", "user_id", "read"),
    )
