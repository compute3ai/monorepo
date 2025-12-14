"""
Render webhook handler - receives render completion notifications and sends results to Telegram.
"""

import asyncio
import logging
from starlette.requests import Request
from starlette.responses import JSONResponse

from services.webhook import validate_webhook, process_webhook_sync, send_telegram_notification

logger = logging.getLogger(__name__)


async def handle_render_webhook(request: Request) -> JSONResponse:
    """
    Handle render completion webhook.

    Returns 200 immediately after validation and spawns background task
    for slow operations (MCP call, LLM caption, Telegram send).

    URL format: /render/<webhook_secret>

    Payload:
    {
        "id": "render-uuid",
        "status": "success" | "failed",
        "result_url": "https://...",  # if success
        "error": "...",  # if failed
    }
    """
    webhook_secret = request.path_params.get("webhook_secret")

    try:
        payload_dict = await request.json()
    except Exception as e:
        logger.warning(f"Invalid JSON payload: {e}")
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    # Validate webhook
    result = validate_webhook(webhook_secret, payload_dict)
    if not result.success:
        return JSONResponse({"error": result.error}, status_code=result.status_code)

    # Process sync operations (fast DB updates)
    process_webhook_sync(result.user, result.payload)

    # Spawn background task for Telegram notification (slow)
    if result.user.telegram_id:
        bot = request.app.state.bot
        asyncio.create_task(
            send_telegram_notification(bot, result.user, result.payload)
        )

    # Return immediately - don't wait for Telegram
    return JSONResponse({"status": "ok"})
