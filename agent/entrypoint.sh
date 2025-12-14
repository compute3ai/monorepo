#!/bin/sh
set -e

# Run migrations (creates tables if fresh db, applies new migrations if existing)
alembic upgrade head

# Start enabled frontends
# Each frontend runs in background except the last one (foreground to keep container alive)

PIDS=""

# Web API
if [ -n "$WEB_PORT" ]; then
    echo "Starting Web API on port $WEB_PORT..."
    python -m frontends.web --port "$WEB_PORT" &
    PIDS="$PIDS $!"
fi

# Telegram
if [ -n "$TELEGRAM_PORT" ]; then
    echo "Starting Telegram frontend on port $TELEGRAM_PORT..."
    python -m frontends.telegram --port "$TELEGRAM_PORT" &
    PIDS="$PIDS $!"
fi

# Discord (future)
if [ -n "$DISCORD_PORT" ]; then
    echo "Starting Discord frontend on port $DISCORD_PORT..."
    python -m frontends.discord --port "$DISCORD_PORT" &
    PIDS="$PIDS $!"
fi

# Check at least one frontend is enabled
if [ -z "$PIDS" ]; then
    echo "Error: No frontends enabled. Set WEB_PORT, TELEGRAM_PORT, or DISCORD_PORT"
    exit 1
fi

# Wait for all background processes
wait $PIDS
