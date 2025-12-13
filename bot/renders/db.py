"""
Database functions for render tracking.
"""

from datetime import datetime
from db import get_session
from .models import UserRender, RenderNotification


# =============================================================================
# UserRender functions
# =============================================================================

def create_render(
    user_id: str,
    thread_id: str,
    render_id: str,
    prompt: str | None = None,
    template: str | None = None,
) -> UserRender:
    """
    Create a render tracking record.

    Call this when MCP tool creates a render, so we can associate
    the webhook response with the correct thread.
    """
    with get_session() as session:
        render = UserRender(
            user_id=user_id,
            thread_id=thread_id,
            render_id=render_id,
            prompt=prompt,
            template=template,
            status="pending",
        )
        session.add(render)
        session.commit()
        session.refresh(render)
        session.expunge(render)
        return render


def get_render_by_render_id(render_id: str) -> UserRender | None:
    """Get a render by its external render_id."""
    with get_session() as session:
        render = session.query(UserRender).filter(
            UserRender.render_id == render_id
        ).first()
        if render:
            session.expunge(render)
        return render


def get_render_by_id(id: int) -> UserRender | None:
    """Get a render by its internal ID."""
    with get_session() as session:
        render = session.query(UserRender).filter(UserRender.id == id).first()
        if render:
            session.expunge(render)
        return render


def update_render_status(
    render_id: str,
    status: str,
    result_url: str | None = None,
    error: str | None = None,
) -> UserRender | None:
    """
    Update render status when webhook arrives.

    Returns the updated render (with thread_id for routing).
    """
    with get_session() as session:
        render = session.query(UserRender).filter(
            UserRender.render_id == render_id
        ).first()
        if not render:
            return None

        render.status = status
        render.result_url = result_url
        render.error = error
        if status in ("success", "failed", "cancelled"):
            render.completed_at = datetime.utcnow()

        session.commit()
        session.refresh(render)
        session.expunge(render)
        return render


def get_pending_renders(user_id: str) -> list[UserRender]:
    """Get all pending renders for a user."""
    with get_session() as session:
        renders = session.query(UserRender).filter(
            UserRender.user_id == user_id,
            UserRender.status == "pending"
        ).order_by(UserRender.created_at.desc()).all()

        for r in renders:
            session.expunge(r)
        return renders


def get_thread_renders(thread_id: str, limit: int = 20) -> list[UserRender]:
    """Get renders for a specific thread."""
    with get_session() as session:
        renders = session.query(UserRender).filter(
            UserRender.thread_id == thread_id
        ).order_by(UserRender.created_at.desc()).limit(limit).all()

        for r in renders:
            session.expunge(r)
        return renders


def get_user_renders(user_id: str, limit: int = 20) -> list[UserRender]:
    """Get all renders for a user, ordered by most recent."""
    with get_session() as session:
        renders = session.query(UserRender).filter(
            UserRender.user_id == user_id
        ).order_by(UserRender.created_at.desc()).limit(limit).all()

        for r in renders:
            session.expunge(r)
        return renders


# =============================================================================
# RenderNotification functions
# =============================================================================

def add_render_notification(
    user_id: str,
    render_id: str,
    status: str,
    result_url: str | None = None,
    error: str | None = None,
) -> RenderNotification:
    """Add a render notification for a user (for web client polling)."""
    with get_session() as session:
        notification = RenderNotification(
            user_id=user_id,
            render_id=render_id,
            status=status,
            result_url=result_url,
            error=error,
        )
        session.add(notification)
        session.commit()
        session.refresh(notification)
        session.expunge(notification)
        return notification


def get_unread_render_notifications(user_id: str, limit: int = 50) -> list[RenderNotification]:
    """Get unread render notifications for a user."""
    with get_session() as session:
        notifications = session.query(RenderNotification).filter(
            RenderNotification.user_id == user_id,
            RenderNotification.read == 0
        ).order_by(RenderNotification.created_at.desc()).limit(limit).all()

        for n in notifications:
            session.expunge(n)
        return notifications


def mark_render_notifications_read(user_id: str, notification_ids: list[int] | None = None) -> int:
    """Mark render notifications as read. Returns count of marked."""
    with get_session() as session:
        query = session.query(RenderNotification).filter(
            RenderNotification.user_id == user_id,
            RenderNotification.read == 0
        )
        if notification_ids:
            query = query.filter(RenderNotification.id.in_(notification_ids))

        count = query.update({"read": 1})
        return count
