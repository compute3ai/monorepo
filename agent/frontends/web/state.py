"""
Shared state for web frontend.

Separated to avoid circular imports between app.py and routes.
"""

# Store active message streams for WebSocket reconnection
# message_id -> {"content": str, "status": str, "subscribers": set[queue]}
active_streams: dict[int, dict] = {}
