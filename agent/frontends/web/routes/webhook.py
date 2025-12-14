"""
Render webhook route.

Handles render completion callbacks at /render/{webhook_secret}.
"""

import logging
from fastapi import APIRouter
from starlette.requests import Request

from services.webhook import validate_webhook, process_webhook_sync

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/render", tags=["webhook"])


@router.post("/{webhook_secret}")
async def render_webhook(request: Request, webhook_secret: str):
    """
    Handle render completion webhook.

    Returns 200 immediately after validation and DB updates.
    Web clients poll for notifications separately.

    Payload:
    {
        "id": "render-uuid",
        "status": "success" | "failed",
        "result_url": "https://...",  # if success
        "error": "...",  # if failed
    }
    """
    try:
        payload_dict = await request.json()
    except Exception:
        return {"error": "Invalid JSON"}, 400

    # Validate webhook
    result = validate_webhook(webhook_secret, payload_dict)
    if not result.success:
        return {"error": result.error}, result.status_code

    # Process sync operations (fast DB updates + notification)
    process_webhook_sync(result.user, result.payload)

    # Return immediately - web clients poll for notifications
    return {"status": "ok"}
