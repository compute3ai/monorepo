"""
Common webhook handler for render completion notifications.

Returns 200 immediately and processes notifications in background.
"""

import asyncio
import json
import logging
from dataclasses import dataclass

from services import renders, users, chats
from config import DEFAULT_MODEL

logger = logging.getLogger(__name__)


@dataclass
class WebhookPayload:
    """Parsed webhook payload."""
    render_id: str
    status: str
    result_url: str | None
    error: str | None


@dataclass
class WebhookResult:
    """Result of webhook validation."""
    success: bool
    error: str | None = None
    status_code: int = 200
    user: object = None
    payload: WebhookPayload | None = None


async def generate_witty_caption(
    api_key: str,
    model: str,
    render_id: str,
    prompt: str | None,
) -> str:
    """Generate a witty caption for a completed render using the LLM."""
    # Late import to avoid circular dependency
    from core import complete

    short_id = render_id[:8] if render_id else "unknown"

    if not prompt:
        return f"Your render is ready! ({short_id})"

    try:
        # Use the prompt itself for language detection - it's already in the user's language
        system_msg = (
            "You are a witty assistant. Generate a SHORT, fun caption (1-2 sentences max) "
            "for an AI-generated image/video. Be playful and creative. Don't use hashtags. "
            "Reference what was in the prompt. "
            "IMPORTANT: Respond in the SAME language as the prompt."
        )

        user_msg = f"The render prompt was: \"{prompt}\"\n\nWrite a witty caption."

        response = await complete(api_key, model, f"{system_msg}\n\n{user_msg}")

        caption = response.strip().strip('"')
        return f"{caption}\n\n({short_id})"
    except Exception as e:
        logger.warning(f"Failed to generate witty caption: {e}")
        return f"Your render is ready! ({short_id})"


def format_render_error_message(render_id: str, error: str) -> str:
    """Format a nice error message for failed renders."""
    short_id = render_id[:8] if render_id else "unknown"
    return f"Your render failed ({short_id})\n\n{error or 'Unknown error'}"


def validate_webhook(webhook_secret: str, payload_dict: dict) -> WebhookResult:
    """
    Validate webhook request and parse payload.

    Returns WebhookResult with success=True if valid, or error details if not.
    """
    user = users.get_user_by_webhook_secret(webhook_secret)
    if not user:
        logger.warning("Invalid webhook secret")
        return WebhookResult(success=False, error="Invalid webhook secret", status_code=403)

    render_id = payload_dict.get("id", "unknown")
    status = payload_dict.get("status")
    result_url = payload_dict.get("result_url")
    error = payload_dict.get("error")

    if not status:
        return WebhookResult(success=False, error="Missing status", status_code=400)

    if status not in ("success", "failed"):
        logger.warning(f"Unknown render status: {status}")
        return WebhookResult(success=False, error=f"Unknown status: {status}", status_code=400)

    payload = WebhookPayload(
        render_id=render_id,
        status=status,
        result_url=result_url,
        error=error,
    )

    return WebhookResult(success=True, user=user, payload=payload)


def process_webhook_sync(user, payload: WebhookPayload) -> None:
    """
    Process webhook synchronously (fast DB operations only).

    This updates the DB and adds notifications - should be fast.
    """
    logger.info(f"Render webhook: user_id={user.user_id} render_id={payload.render_id} status={payload.status}")

    # Update render status in DB
    renders.update_render_status(payload.render_id, payload.status, payload.result_url, payload.error)

    # Add notification for web clients (polling)
    renders.add_render_notification(user.user_id, payload.render_id, payload.status, payload.result_url, payload.error)


async def send_telegram_notification(
    bot,
    user,
    payload: WebhookPayload,
) -> None:
    """
    Send Telegram notification for render completion.

    This is the slow operation that should run in background.
    """
    # Late import to avoid circular dependency
    from core import call_mcp_tool

    try:
        if payload.status == "success" and payload.result_url:
            # Try to get render details for prompt
            prompt = None
            if user.api_key:
                try:
                    render_details = await call_mcp_tool(user.api_key, "get_render", {"render_id": payload.render_id})
                    if isinstance(render_details, str):
                        data = json.loads(render_details)
                        prompt = data.get("params", {}).get("prompt") or data.get("prompt")
                    elif isinstance(render_details, dict):
                        prompt = render_details.get("params", {}).get("prompt") or render_details.get("prompt")
                except Exception as e:
                    logger.warning(f"Failed to fetch render details: {e}")

            # Generate caption using the render's prompt (not chat history)
            model = user.model or DEFAULT_MODEL
            if user.api_key and prompt:
                caption = await generate_witty_caption(user.api_key, model, payload.render_id, prompt)
            else:
                short_id = payload.render_id[:8] if payload.render_id else "unknown"
                caption = f"Your render is ready! ({short_id})"

            # Determine if video or image
            is_video = any(ext in payload.result_url.lower() for ext in ['.mp4', '.webm', '.mov', '.avi'])

            try:
                if is_video:
                    await bot.send_video(chat_id=user.telegram_id, video=payload.result_url, caption=caption)
                else:
                    await bot.send_photo(chat_id=user.telegram_id, photo=payload.result_url, caption=caption)
                logger.info(f"Sent render result to chat {user.telegram_id}")
            except Exception as e:
                logger.error(f"Failed to send render media: {e}")
                try:
                    await bot.send_message(chat_id=user.telegram_id, text=f"{caption}\n\n{payload.result_url}")
                except Exception as e2:
                    logger.error(f"Failed to send render URL: {e2}")

        elif payload.status == "failed":
            message = format_render_error_message(payload.render_id, payload.error)
            try:
                await bot.send_message(chat_id=user.telegram_id, text=message)
            except Exception as e:
                logger.error(f"Failed to send error message: {e}")

    except Exception as e:
        logger.error(f"Error in Telegram notification background task: {e}")
