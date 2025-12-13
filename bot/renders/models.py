"""
Render models for tracking user renders.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Index

# Import Base from parent db module
from db import Base


class UserRender(Base):
    """
    Track user renders and their thread associations.

    When a render is created via MCP tool, we store it here with the thread_id.
    When the webhook arrives, we can look up the thread to add the result.
    """
    __tablename__ = "user_renders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False, index=True)
    thread_id = Column(String, ForeignKey("threads.id"), nullable=False, index=True)
    render_id = Column(String, nullable=False, unique=True, index=True)  # External render service ID
    prompt = Column(Text, nullable=True)  # Original prompt for context
    template = Column(String, nullable=True)  # Template used (e.g., "video_wan2_2_14B_t2v")
    status = Column(String, nullable=False, default="pending")  # pending, success, failed, cancelled
    result_url = Column(String, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_user_renders_user_status", "user_id", "status"),
    )


class RenderNotification(Base):
    """
    Store render completion notifications for web clients.
    Telegram users get push notifications; web clients poll this table.
    """
    __tablename__ = "render_notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False, index=True)
    render_id = Column(String, nullable=False)
    status = Column(String, nullable=False)  # success, failed
    result_url = Column(String, nullable=True)
    error = Column(Text, nullable=True)
    read = Column(Integer, default=0)  # 0=unread, 1=read
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_render_notifications_user_unread", "user_id", "read"),
    )
