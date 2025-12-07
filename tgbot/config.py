"""
Configuration for the Telegram bot.
"""

import os

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_PREFIX = os.getenv("WEBHOOK_PREFIX")  # e.g., https://api.compute3.ai/tgbot

# Compute3 API
API_BASE_URL = os.getenv("API_BASE_URL", "https://api.compute3.ai")

# Models
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "hermes4:70b")

# MCP
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL")  # Optional MCP server

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./tgbot.db")

# Server
PORT = int(os.getenv("PORT", "8000"))

# Validation
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN required")
if not WEBHOOK_PREFIX:
    raise ValueError("WEBHOOK_PREFIX required")
