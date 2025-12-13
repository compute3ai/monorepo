"""
Configuration for the Compute3 Bot.

Either TELEGRAM_BOT_TOKEN or API_PORT (or both) must be set.
"""

import os

# Telegram (optional - only start bot if set)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_PREFIX = os.getenv("WEBHOOK_PREFIX")  # e.g., https://api.compute3.ai/bot/tg

# Compute3 API
API_BASE_URL = os.getenv("API_BASE_URL", "https://api.compute3.ai")

# Models
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL")

# MCP
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL")  # Optional MCP server

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./bot.db")

# Server
PORT = int(os.getenv("PORT", "8000"))  # Telegram webhook port
API_PORT = os.getenv("API_PORT")  # REST API port - if set, enables REST API

# Derived flags
ENABLE_TELEGRAM = bool(TELEGRAM_BOT_TOKEN)
ENABLE_REST_API = bool(API_PORT)

# Convert API_PORT to int if set
if API_PORT:
    API_PORT = int(API_PORT)

# Validation
if not DEFAULT_MODEL:
    raise ValueError("DEFAULT_MODEL required")

if ENABLE_TELEGRAM and not WEBHOOK_PREFIX:
    raise ValueError("WEBHOOK_PREFIX required when TELEGRAM_BOT_TOKEN is set")

if not ENABLE_TELEGRAM and not ENABLE_REST_API:
    raise ValueError("At least one of TELEGRAM_BOT_TOKEN or API_PORT must be set")
