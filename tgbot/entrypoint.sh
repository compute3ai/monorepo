#!/bin/sh
set -e

# Run migrations (creates tables if fresh db, applies new migrations if existing)
alembic upgrade head

# Start bot
exec python bot.py
