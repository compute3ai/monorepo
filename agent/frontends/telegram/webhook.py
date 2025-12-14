"""
Render webhook handler - receives render completion notifications and sends results to Telegram.
"""

import json
import logging
from starlette.requests import Request
from starlette.responses import JSONResponse
from telegram import Bot

from config import DEFAULT_MODEL
from services import users, chats, renders
from core import call_mcp_tool, complete

logger = logging.getLogger(__name__)


async def generate_witty_caption(
    api_key: str,
    model: str,
    render_id: str,
    prompt: str | None,
    user_last_message: str | None = None,
) -> str:
    """Generate a witty caption for a completed render using the LLM."""
    short_id = render_id[:8] if render_id else "unknown"

    if not prompt:
        return f"Your render is ready! ({short_id})"

    try:
        system_msg = (
            "You are a witty assistant. Generate a SHORT, fun caption (1-2 sentences max) "
            "for an AI-generated image. Be playful and creative. Don't use hashtags. "
            "Reference what was in the prompt. "
        )

        if user_last_message:
            system_msg += (
                f"\n\nIMPORTANT: Detect the language from the user's last message and respond in that SAME language. "
                f"User's last message: \"{user_last_message}\""
            )

        user_msg = f"The user requested: \"{prompt}\"\n\nWrite a witty caption for the completed render."

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


async def handle_render_webhook(request: Request) -> JSONResponse:
    """
    Handle render completion webhook.

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

    user = users.get_user_by_webhook_secret(webhook_secret)
    if not user:
        logger.warning("Invalid webhook secret")
        return JSONResponse({"error": "Invalid webhook secret"}, status_code=403)

    try:
        payload = await request.json()
    except Exception as e:
        logger.warning(f"Invalid JSON payload: {e}")
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    render_id = payload.get("id", "unknown")
    status = payload.get("status")
    result_url = payload.get("result_url")
    error = payload.get("error")

    logger.info(f"Render webhook: user_id={user.user_id} render_id={render_id} status={status}")

    # Update render status in DB
    renders.update_render_status(render_id, status, result_url, error)

    # Add notification for web clients
    renders.add_render_notification(user.user_id, render_id, status, result_url, error)

    # If Telegram user, send message
    if user.telegram_id:
        bot: Bot = request.app.state.bot

        if status == "success" and result_url:
            # Try to get render details for prompt
            prompt = None
            if user.api_key:
                try:
                    render_details = await call_mcp_tool(user.api_key, "get_render", {"render_id": render_id})
                    if isinstance(render_details, str):
                        data = json.loads(render_details)
                        prompt = data.get("params", {}).get("prompt") or data.get("prompt")
                    elif isinstance(render_details, dict):
                        prompt = render_details.get("params", {}).get("prompt") or render_details.get("prompt")
                except Exception as e:
                    logger.warning(f"Failed to fetch render details: {e}")

            # Get last message for language detection
            user_last_message = chats.get_last_user_message(user.user_id)

            # Generate caption
            model = user.model or DEFAULT_MODEL
            if user.api_key and prompt:
                caption = await generate_witty_caption(user.api_key, model, render_id, prompt, user_last_message)
            else:
                short_id = render_id[:8] if render_id else "unknown"
                caption = f"Your render is ready! ({short_id})"

            # Determine if video or image
            is_video = any(ext in result_url.lower() for ext in ['.mp4', '.webm', '.mov', '.avi'])

            try:
                if is_video:
                    await bot.send_video(chat_id=user.telegram_id, video=result_url, caption=caption)
                else:
                    await bot.send_photo(chat_id=user.telegram_id, photo=result_url, caption=caption)
                logger.info(f"Sent render result to chat {user.telegram_id}")
            except Exception as e:
                logger.error(f"Failed to send render media: {e}")
                try:
                    await bot.send_message(chat_id=user.telegram_id, text=f"{caption}\n\n{result_url}")
                except Exception as e2:
                    logger.error(f"Failed to send render URL: {e2}")
                    return JSONResponse({"error": str(e2)}, status_code=500)

        elif status == "failed":
            message = format_render_error_message(render_id, error)
            try:
                await bot.send_message(chat_id=user.telegram_id, text=message)
            except Exception as e:
                logger.error(f"Failed to send error message: {e}")
                return JSONResponse({"error": str(e)}, status_code=500)

        else:
            logger.warning(f"Unknown render status: {status}")
            return JSONResponse({"error": f"Unknown status: {status}"}, status_code=400)

    return JSONResponse({"status": "ok"})
