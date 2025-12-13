"""
Renders module - tracking user renders and their thread associations.
"""

from .models import UserRender, RenderNotification
from .db import (
    # UserRender functions
    create_render,
    get_render_by_render_id,
    get_render_by_id,
    update_render_status,
    get_pending_renders,
    get_thread_renders,
    get_user_renders,
    # RenderNotification functions
    add_render_notification,
    get_unread_render_notifications,
    mark_render_notifications_read,
)

__all__ = [
    "UserRender",
    "RenderNotification",
    "create_render",
    "get_render_by_render_id",
    "get_render_by_id",
    "update_render_status",
    "get_pending_renders",
    "get_thread_renders",
    "get_user_renders",
    "add_render_notification",
    "get_unread_render_notifications",
    "mark_render_notifications_read",
]
