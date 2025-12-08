"""
Compute3 Telegram Bot - AI chat with MCP tools.
"""

import logging
import sys
import asyncio

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import Response
import uvicorn

from config import TELEGRAM_BOT_TOKEN, WEBHOOK_PREFIX, PORT
from handlers.onboarding import cmd_start, handle_api_key_input
from handlers.chat import handle_message, cmd_newcontext
from handlers.settings import handle_settings_callback
from handlers.webhook import handle_render_webhook

import os
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


async def telegram_webhook(request):
    """Handle Telegram webhook updates."""
    app = request.app
    application: Application = app.state.application

    try:
        data = await request.json()
        update = Update.de_json(data, application.bot)
        # Process update in background, don't block webhook response
        asyncio.create_task(application.process_update(update))
    except Exception as e:
        logger.error(f"Error processing Telegram update: {e}")

    # Return 200 immediately so Telegram doesn't retry
    return Response(status_code=200)


async def health_check(request):
    """Health check endpoint."""
    return Response(content="OK", status_code=200)


def create_app() -> Starlette:
    """Create the Starlette application with all routes."""
    logger.info("Starting Compute3 Telegram Bot")
    logger.info(f"Webhook URL: {WEBHOOK_PREFIX}")

    # Build Telegram application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Command handlers
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("newcontext", cmd_newcontext))
    application.add_handler(CommandHandler("new", cmd_newcontext))  # Alias

    # Callback query handler for inline buttons
    application.add_handler(CallbackQueryHandler(handle_settings_callback))

    # Message handler for chat and API key input
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Create Starlette app with routes
    routes = [
        # Telegram webhook
        Route(f"/webhook/{TELEGRAM_BOT_TOKEN}", telegram_webhook, methods=["POST"]),
        # Render completion webhook (user identified by their unique webhook_secret)
        Route("/render/{webhook_secret}", handle_render_webhook, methods=["POST"]),
        # Health check
        Route("/health", health_check, methods=["GET"]),
    ]

    async def on_startup():
        """Initialize Telegram application and set webhook."""
        await application.initialize()
        await application.start()

        # Set webhook URL
        webhook_url = f"{WEBHOOK_PREFIX}/webhook/{TELEGRAM_BOT_TOKEN}"
        await application.bot.set_webhook(
            url=webhook_url,
            allowed_updates=Update.ALL_TYPES,
        )
        logger.info(f"Webhook set to: {webhook_url}")

        # Prefetch MCP tools at startup (no auth needed for listing)
        from services.mcp import get_mcp_tools
        try:
            tools = await get_mcp_tools()
            logger.info(f"Prefetched {len(tools)} MCP tools at startup")
        except Exception as e:
            logger.warning(f"Failed to prefetch MCP tools: {e}")

    async def on_shutdown():
        """Cleanup Telegram application."""
        await application.stop()
        await application.shutdown()

    app = Starlette(
        routes=routes,
        on_startup=[on_startup],
        on_shutdown=[on_shutdown],
    )

    # Store application and bot in app state for access in route handlers
    app.state.application = application
    app.state.bot = application.bot

    return app


def main():
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")


if __name__ == "__main__":
    main()
