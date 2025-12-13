"""
Render webhook handler - receives render completion notifications and sends results to Telegram.
"""

import json
import logging
from starlette.requests import Request
from starlette.responses import JSONResponse
from telegram import Bot

from db import get_user_by_webhook_secret, get_last_user_message
from services.mcp import call_mcp_tool
from services.inference import chat_completion

logger = logging.getLogger(__name__)


async def generate_witty_caption(api_key: str, model: str, render_id: str, prompt: str | None, user_last_message: str | None = None) -> str:
    """Generate a witty caption for a completed render using the LLM."""
    short_id = render_id[:8] if render_id else "unknown"

    if not prompt:
        return f"✨ Your render is ready! ({short_id})"

    try:
        # Build system prompt with language detection
        system_msg = (
            "You are a witty assistant. Generate a SHORT, fun caption (1-2 sentences max) "
            "for an AI-generated image. Be playful and creative. Don't use hashtags. "
            "Reference what was in the prompt. "
        )

        # Add language detection if we have the user's last message
        if user_last_message:
            system_msg += (
                f"\n\nIMPORTANT: Detect the language from the user's last message and respond in that SAME language. "
                f"User's last message: \"{user_last_message}\""
            )

        user_msg = f"The user requested: \"{prompt}\"\n\nWrite a witty caption for the completed render."

        response = await chat_completion(api_key, model, f"{system_msg}\n\n{user_msg}")

        # Clean up response and add render ID
        caption = response.strip().strip('"')
        return f"{caption}\n\n({short_id})"
    except Exception as e:
        logger.warning(f"Failed to generate witty caption: {e}")
        return f"✨ Your render is ready! ({short_id})"


def format_render_error_message(render_id: str, error: str) -> str:
    """Format a nice error message for failed renders."""
    short_id = render_id[:8] if render_id else "unknown"
    return (
        f"❌ Your render failed ({short_id})\n\n"
        f"{error or 'Unknown error'}"
    )


async def handle_render_webhook(request: Request) -> JSONResponse:
    """
    Handle render completion webhook.

    URL format: /render/<webhook_secret>

    The webhook_secret is unique per user, so we look up the user by it.

    Payload:
    {
        "id": "render-uuid",
        "status": "success" | "failed",
        "result_url": "https://...",  # if success
        "error": "...",  # if failed
    }
    """
    # Extract webhook_secret from path
    webhook_secret = request.path_params.get("webhook_secret")

    # Look up user by webhook secret
    user = get_user_by_webhook_secret(webhook_secret)
    if not user:
        logger.warning(f"Invalid webhook secret")
        return JSONResponse({"error": "Invalid webhook secret"}, status_code=403)

    chat_id = user.chat_id

    # Parse payload
    try:
        payload = await request.json()
    except Exception as e:
        logger.warning(f"Invalid JSON payload: {e}")
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    render_id = payload.get("id", "unknown")
    status = payload.get("status")
    result_url = payload.get("result_url")
    error = payload.get("error")

    logger.info(f"Render webhook: chat_id={chat_id} render_id={render_id} status={status}")

    # Get bot from app state
    bot: Bot = request.app.state.bot

    if status == "success" and result_url:
        # Try to fetch render details to get the prompt
        prompt = None
        if user.api_key:
            try:
                render_details = await call_mcp_tool(user.api_key, "get_render", {"render_id": render_id})
                # Parse JSON response to get prompt
                if isinstance(render_details, str):
                    data = json.loads(render_details)
                    prompt = data.get("params", {}).get("prompt") or data.get("prompt")
                elif isinstance(render_details, dict):
                    prompt = render_details.get("params", {}).get("prompt") or render_details.get("prompt")
            except Exception as e:
                logger.warning(f"Failed to fetch render details: {e}")

        # Get user's last message for language detection
        user_last_message = get_last_user_message(chat_id)

        # Generate witty caption
        model = user.model or "hermes4:70b"
        if user.api_key and prompt:
            caption = await generate_witty_caption(user.api_key, model, render_id, prompt, user_last_message)
        else:
            short_id = render_id[:8] if render_id else "unknown"
            caption = f"✨ Your render is ready! ({short_id})"

        # Determine if it's an image or video based on URL
        is_video = any(ext in result_url.lower() for ext in ['.mp4', '.webm', '.mov', '.avi'])

        try:
            if is_video:
                await bot.send_video(
                    chat_id=chat_id,
                    video=result_url,
                    caption=caption,
                )
            else:
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=result_url,
                    caption=caption,
                )
            logger.info(f"Sent render result to chat {chat_id}")
        except Exception as e:
            logger.error(f"Failed to send render media: {e}")
            # Try sending just the URL as text
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"{caption}\n\n{result_url}",
                )
            except Exception as e2:
                logger.error(f"Failed to send render URL: {e2}")
                return JSONResponse({"error": str(e2)}, status_code=500)

    elif status == "failed":
        message = format_render_error_message(render_id, error)
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=message,
            )
        except Exception as e:
            logger.error(f"Failed to send error message: {e}")
            return JSONResponse({"error": str(e)}, status_code=500)

    else:
        logger.warning(f"Unknown render status: {status}")
        return JSONResponse({"error": f"Unknown status: {status}"}, status_code=400)

    return JSONResponse({"status": "ok"})
