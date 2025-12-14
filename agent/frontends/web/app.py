"""
FastAPI application with REST + WebSocket endpoints.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.mcp import get_mcp_tools

from .routes.chats import router as chats_router
from .routes.renders import router as renders_router
from .routes.users import router as users_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown."""
    logger.info("Starting Compute3 Agent Web API")

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
    app = FastAPI(
        title="Compute3 Agent API",
        description="AI chat agent with GPU compute tools",
        version="0.1.0",
        lifespan=lifespan,
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
    app.include_router(chats_router)
    app.include_router(renders_router)
    app.include_router(users_router)

    # Health check (no auth)
    @app.get("/health", tags=["health"])
    async def health_check():
        """Health check endpoint."""
        return {"status": "ok"}

    return app


