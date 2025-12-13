#!/bin/sh
set -e

# Run migrations (creates tables if fresh db, applies new migrations if existing)
alembic upgrade head

# Track if we started something
STARTED=""

# Start REST API if API_PORT is set
if [ -n "$API_PORT" ]; then
    echo "Starting REST API on port $API_PORT..."
    if [ -n "$TELEGRAM_BOT_TOKEN" ]; then
        # Both services - run API in background
        uvicorn api:app --host 0.0.0.0 --port "$API_PORT" &
        STARTED="api"
    else
        # Only API - run in foreground
        exec uvicorn api:app --host 0.0.0.0 --port "$API_PORT"
    fi
fi

# Start Telegram bot if token is set
if [ -n "$TELEGRAM_BOT_TOKEN" ]; then
    echo "Starting Telegram bot on port $PORT..."
    exec python bot.py
fi

# Should not reach here due to config validation, but just in case
echo "Error: Neither TELEGRAM_BOT_TOKEN nor API_PORT is set"
exit 1
