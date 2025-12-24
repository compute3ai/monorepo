"""
FastAPI application with REST + WebSocket endpoints.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional

import jwt
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from config import URL_PREFIX
from core.mcp import get_mcp_tools

from .routes.chats import router as chats_router, active_streams
from .routes.renders import router as renders_router
from .routes.users import router as users_router
from .routes.webhook import router as webhook_router
from .dependencies import JWT_VERIFY, PUBLIC_KEY

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown."""
    logger.info("Starting Compute3 Agent Web API")
    logger.info(f"URL prefix: {URL_PREFIX}")

    # Prefetch MCP tools
    try:
        tools = await get_mcp_tools()
        logger.info(f"Prefetched {len(tools)} MCP tools")
    except Exception as e:
        logger.warning(f"Failed to prefetch MCP tools: {e}")

    yield

    logger.info("Shutting down Compute3 Agent Web API")


def create_app() -> FastAPI:
    """Create FastAPI application."""
    prefix = f"{URL_PREFIX}/api"

    app = FastAPI(
        title="Compute3 Agent API",
        description="AI chat agent with GPU compute tools",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=f"{prefix}/docs",
        redoc_url=f"{prefix}/redoc",
        openapi_url=f"{prefix}/openapi.json",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(chats_router, prefix=prefix)
    app.include_router(renders_router, prefix=prefix)
    app.include_router(users_router, prefix=prefix)
    app.include_router(webhook_router, prefix=prefix)

    # Health check (no auth)
    @app.get(f"{prefix}/health", tags=["health"])
    async def health_check():
        """Health check endpoint."""
        return {"status": "ok"}

    # User-level WebSocket for streaming - persistent connection
    @app.websocket(f"{prefix}/stream")
    async def stream_user(websocket: WebSocket):
        """
        User-level WebSocket endpoint for streaming chat responses.

        Connect once per session, subscribe to message streams as needed.
        Survives chat switches without reconnection.

        Messages:
        - {"type": "subscribe", "message_id": 123} - Subscribe to a message stream
        - {"type": "unsubscribe"} - Unsubscribe from current stream
        - {"type": "token", "content": "..."} - Token update (full content so far)
        - {"type": "done", "content": "..."} - Stream complete
        - {"type": "error", "error": "..."} - Error occurred
        """
        await websocket.accept()

        # JWT auth via query param
        token = websocket.query_params.get("token")
        if not token:
            await websocket.close(code=4001, reason="Missing token")
            return

        # Validate JWT and extract user_id
        try:
            if JWT_VERIFY:
                payload = jwt.decode(token, PUBLIC_KEY, algorithms=["ES256"])
            else:
                payload = jwt.decode(token, options={"verify_signature": False})

            user_id = payload.get("user_id")
            if not user_id:
                await websocket.close(code=4001, reason="Token missing user_id")
                return
        except jwt.ExpiredSignatureError:
            await websocket.close(code=4001, reason="Token expired")
            return
        except jwt.InvalidTokenError as e:
            await websocket.close(code=4001, reason=f"Invalid token: {e}")
            return

        logger.info(f"[WS] User {user_id} connected to stream")

        # Queue for this connection
        queue: asyncio.Queue = asyncio.Queue()
        subscribed_message_id: Optional[int] = None

        async def handle_client_messages():
            """Handle incoming WebSocket messages from client."""
            nonlocal subscribed_message_id
            try:
                while True:
                    data = await websocket.receive_json()
                    msg_type = data.get("type")

                    if msg_type == "subscribe":
                        message_id = data.get("message_id")
                        logger.info(f"[WS] User {user_id} subscribe request for message_id={message_id}")

                        if message_id and message_id in active_streams:
                            # Unsubscribe from previous
                            if subscribed_message_id and subscribed_message_id in active_streams:
                                active_streams[subscribed_message_id]["subscribers"].discard(queue)

                            # Subscribe to new
                            subscribed_message_id = message_id
                            active_streams[message_id]["subscribers"].add(queue)
                            logger.info(f"[WS] Subscribed, now {len(active_streams[message_id]['subscribers'])} subscribers")

                            # Send current state
                            state = active_streams[message_id]
                            await websocket.send_json({
                                "type": "state",
                                "content": state["content"],
                                "status": state["status"],
                            })
                        else:
                            logger.warning(f"[WS] Message {message_id} not in active_streams")
                            await websocket.send_json({
                                "type": "error",
                                "error": f"Message {message_id} not found in active streams",
                            })

                    elif msg_type == "unsubscribe":
                        if subscribed_message_id and subscribed_message_id in active_streams:
                            active_streams[subscribed_message_id]["subscribers"].discard(queue)
                            logger.info(f"[WS] User {user_id} unsubscribed from message {subscribed_message_id}")
                        subscribed_message_id = None

                    elif msg_type == "ping":
                        await websocket.send_json({"type": "pong"})

            except WebSocketDisconnect:
                pass

        async def handle_queue_messages():
            """Forward queue messages to WebSocket."""
            try:
                while True:
                    event = await queue.get()
                    await websocket.send_json(event)
            except WebSocketDisconnect:
                pass

        try:
            # Run both handlers concurrently
            await asyncio.gather(
                handle_client_messages(),
                handle_queue_messages(),
                return_exceptions=True,
            )
        except WebSocketDisconnect:
            pass
        finally:
            # Cleanup
            logger.info(f"[WS] User {user_id} disconnected from stream")
            if subscribed_message_id and subscribed_message_id in active_streams:
                active_streams[subscribed_message_id]["subscribers"].discard(queue)

    return app


