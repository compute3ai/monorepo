"""
Core module - inference, MCP tools, prompts, session management.
"""

from .inference import (
    stream_completion,
    complete,
    execute_confirmed_tool,
    StreamEvent,
    TOOLS_REQUIRING_CONFIRMATION,
)
from .mcp import get_mcp_tools, call_mcp_tool
from .prompts import build_system_prompt
from .session import BaseChatSession, SessionContext

__all__ = [
    "stream_completion",
    "complete",
    "execute_confirmed_tool",
    "StreamEvent",
    "TOOLS_REQUIRING_CONFIRMATION",
    "get_mcp_tools",
    "call_mcp_tool",
    "build_system_prompt",
    "BaseChatSession",
    "SessionContext",
]
