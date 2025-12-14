"""
Configuration for the Compute3 Agent.

Frontends are enabled via entrypoint.sh based on *_PORT env vars.
"""

import os

# API base URL (e.g., https://api.compute3.ai)
API_BASE_URL = os.getenv("API_BASE_URL", "https://api.compute3.ai")

# URL prefix for routes (e.g., /agent)
URL_PREFIX = os.getenv("URL_PREFIX", "")

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Models
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "minimax-m2")
