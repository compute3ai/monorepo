"""
Telegram Starlette application - webhook server.
"""

import logging
import sys
import asyncio
import os

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

from config import TELEGRAM_BOT_TOKEN, API_BASE_URL, URL_PREFIX
from .handlers import cmd_start, cmd_newcontext, handle_message, handle_callback
from .webhook import handle_render_webhook

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
    application: Application = request.app.state.application

    try:
        data = await request.json()
        update = Update.de_json(data, application.bot)
        asyncio.create_task(application.process_update(update))
    except Exception as e:
        logger.error(f"Error processing Telegram update: {e}")

    return Response(status_code=200)


async def health_check(request):
    """Health check endpoint."""
    return Response(content="OK", status_code=200)


def create_app() -> Starlette:
    """Create the Starlette application with all routes."""
    logger.info("Starting Compute3 Telegram Agent")
    logger.info(f"API base URL: {API_BASE_URL}")
    logger.info(f"URL prefix: {URL_PREFIX}")

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Command handlers
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("newcontext", cmd_newcontext))
    application.add_handler(CommandHandler("new", cmd_newcontext))

    # Callback query handler
    application.add_handler(CallbackQueryHandler(handle_callback))

    # Message handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    routes = [
        Route(f"{URL_PREFIX}/tg/webhook/{TELEGRAM_BOT_TOKEN}", telegram_webhook, methods=["POST"]),
        Route(f"{URL_PREFIX}/tg/render/{{webhook_secret}}", handle_render_webhook, methods=["POST"]),
        Route(f"{URL_PREFIX}/tg/health", health_check, methods=["GET"]),
    ]

    async def on_startup():
        await application.initialize()
        await application.start()

        webhook_url = f"{API_BASE_URL}{URL_PREFIX}/tg/webhook/{TELEGRAM_BOT_TOKEN}"
        await application.bot.set_webhook(url=webhook_url, allowed_updates=Update.ALL_TYPES)
        logger.info(f"Webhook set to: {webhook_url}")

        # Prefetch MCP tools
        from core import get_mcp_tools
        try:
            tools = await get_mcp_tools()
            logger.info(f"Prefetched {len(tools)} MCP tools at startup")
        except Exception as e:
            logger.warning(f"Failed to prefetch MCP tools: {e}")

    async def on_shutdown():
        await application.stop()
        await application.shutdown()

    app = Starlette(
        routes=routes,
        on_startup=[on_startup],
        on_shutdown=[on_shutdown],
    )

    app.state.application = application
    app.state.bot = application.bot

    return app


