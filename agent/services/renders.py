"""
Render service - render tracking functions.
"""

from datetime import datetime
from db.models import get_session, Render, RenderNotification


def create_render(
    user_id: str,
    chat_id: str,
    render_id: str,
    prompt: str | None = None,
    template: str | None = None,
) -> Render:
    """Create a render tracking record."""
    with get_session() as session:
        render = Render(
            user_id=user_id,
            chat_id=chat_id,
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


def get_render(id: int) -> Render | None:
    """Get a render by its internal ID."""
    with get_session() as session:
        render = session.query(Render).filter(Render.id == id).first()
        if render:
            session.expunge(render)
        return render


def get_render_by_render_id(render_id: str) -> Render | None:
    """Get a render by its external render_id."""
    with get_session() as session:
        render = session.query(Render).filter(Render.render_id == render_id).first()
        if render:
            session.expunge(render)
        return render


def update_render_status(
    render_id: str,
    status: str,
    result_url: str | None = None,
    error: str | None = None,
) -> Render | None:
    """Update render status when webhook arrives."""
    with get_session() as session:
        render = session.query(Render).filter(Render.render_id == render_id).first()
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


def get_pending_renders(user_id: str) -> list[Render]:
    """Get all pending renders for a user."""
    with get_session() as session:
        renders = session.query(Render).filter(
            Render.user_id == user_id,
            Render.status == "pending"
        ).order_by(Render.created_at.desc()).all()

        for r in renders:
            session.expunge(r)
        return renders


def get_chat_renders(chat_id: str, limit: int = 20) -> list[Render]:
    """Get renders for a specific chat."""
    with get_session() as session:
        renders = session.query(Render).filter(
            Render.chat_id == chat_id
        ).order_by(Render.created_at.desc()).limit(limit).all()

        for r in renders:
            session.expunge(r)
        return renders


def get_user_renders(user_id: str, limit: int = 20) -> list[Render]:
    """Get all renders for a user, ordered by most recent."""
    with get_session() as session:
        renders = session.query(Render).filter(
            Render.user_id == user_id
        ).order_by(Render.created_at.desc()).limit(limit).all()

        for r in renders:
            session.expunge(r)
        return renders


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


def get_unread_notifications(user_id: str, limit: int = 50) -> list[RenderNotification]:
    """Get unread render notifications for a user."""
    with get_session() as session:
        notifications = session.query(RenderNotification).filter(
            RenderNotification.user_id == user_id,
            RenderNotification.read == 0
        ).order_by(RenderNotification.created_at.desc()).limit(limit).all()

        for n in notifications:
            session.expunge(n)
        return notifications


def mark_notifications_read(user_id: str, notification_ids: list[int] | None = None) -> int:
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
