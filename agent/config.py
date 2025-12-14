"""
Configuration for the Compute3 Agent.

Frontends are enabled via entrypoint.sh based on *_PORT env vars.
"""

import os

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_PREFIX = os.getenv("WEBHOOK_PREFIX")  # e.g., https://api.compute3.ai/agent/tg

# Compute3 API
API_BASE_URL = os.getenv("API_BASE_URL", "https://api.compute3.ai")

# Models
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "minimax-m2")
