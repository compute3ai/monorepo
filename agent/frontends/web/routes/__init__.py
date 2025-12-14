"""
Web API routes.
"""

from .chats import router as chats_router
from .renders import router as renders_router
from .users import router as users_router

__all__ = ["chats_router", "renders_router", "users_router"]
