"""
Renders API routes.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from frontends.web.dependencies import require_api_key
from services import renders

router = APIRouter(prefix="/renders", tags=["renders"])


# =============================================================================
# Pydantic models
# =============================================================================


class RenderResponse(BaseModel):
    id: int
    render_id: str
    chat_id: str
    prompt: Optional[str]
    template: Optional[str]
    status: str
    result_url: Optional[str]
    error: Optional[str]
    created_at: str
    completed_at: Optional[str]


class NotificationResponse(BaseModel):
    id: int
    render_id: str
    status: str
    result_url: Optional[str]
    error: Optional[str]
    created_at: str


# =============================================================================
# REST endpoints
# =============================================================================


@router.get("", response_model=list[RenderResponse])
async def list_renders(
    limit: int = 20,
    user_id: str = Depends(require_api_key),
):
    """List user's renders."""
    render_list = renders.get_user_renders(user_id, limit)
    return [
        RenderResponse(
            id=r.id,
            render_id=r.render_id,
            chat_id=r.chat_id,
            prompt=r.prompt,
            template=r.template,
            status=r.status,
            result_url=r.result_url,
            error=r.error,
            created_at=r.created_at.isoformat(),
            completed_at=r.completed_at.isoformat() if r.completed_at else None,
        )
        for r in render_list
    ]


@router.get("/pending", response_model=list[RenderResponse])
async def list_pending_renders(
    user_id: str = Depends(require_api_key),
):
    """List user's pending renders."""
    render_list = renders.get_pending_renders(user_id)
    return [
        RenderResponse(
            id=r.id,
            render_id=r.render_id,
            chat_id=r.chat_id,
            prompt=r.prompt,
            template=r.template,
            status=r.status,
            result_url=r.result_url,
            error=r.error,
            created_at=r.created_at.isoformat(),
            completed_at=r.completed_at.isoformat() if r.completed_at else None,
        )
        for r in render_list
    ]


@router.get("/notifications", response_model=list[NotificationResponse])
async def get_notifications(
    limit: int = 50,
    user_id: str = Depends(require_api_key),
):
    """Get unread render notifications."""
    notifications = renders.get_unread_notifications(user_id, limit)
    return [
        NotificationResponse(
            id=n.id,
            render_id=n.render_id,
            status=n.status,
            result_url=n.result_url,
            error=n.error,
            created_at=n.created_at.isoformat(),
        )
        for n in notifications
    ]


@router.post("/notifications/read")
async def mark_notifications_read(
    notification_ids: Optional[list[int]] = None,
    user_id: str = Depends(require_api_key),
):
    """Mark render notifications as read."""
    count = renders.mark_notifications_read(user_id, notification_ids)
    return {"marked": count}


@router.get("/{render_id}", response_model=RenderResponse)
async def get_render(
    render_id: str,
    user_id: str = Depends(require_api_key),
):
    """Get a render by ID."""
    render = renders.get_render_by_render_id(render_id)
    if not render or render.user_id != user_id:
        raise HTTPException(status_code=404, detail="Render not found")

    return RenderResponse(
        id=render.id,
        render_id=render.render_id,
        chat_id=render.chat_id,
        prompt=render.prompt,
        template=render.template,
        status=render.status,
        result_url=render.result_url,
        error=render.error,
        created_at=render.created_at.isoformat(),
        completed_at=render.completed_at.isoformat() if render.completed_at else None,
    )


