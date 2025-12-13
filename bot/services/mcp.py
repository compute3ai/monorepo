"""
MCP (Model Context Protocol) client service for tool integration.
"""

import logging
from typing import Any
from fastmcp.client import Client, StreamableHttpTransport

from config import API_BASE_URL

logger = logging.getLogger(__name__)

MCP_URL = f"{API_BASE_URL}/mcp"

# Tools cache (global - same for all users, cached forever, restart bot to refresh)
_tools_cache: list[dict] | None = None

# Auth params that are handled automatically by MCP transport - strip from tool schemas
AUTH_PARAMS = {"X-API-KEY", "Authorization", "X-Api-Key"}


def strip_auth_params(schema: dict) -> dict:
    """Remove auth parameters from tool schema - they're handled by MCP transport."""
    if not schema or "properties" not in schema:
        return schema

    schema = schema.copy()
    props = {k: v for k, v in schema.get("properties", {}).items() if k not in AUTH_PARAMS}
    schema["properties"] = props

    # Also remove from required if present
    if "required" in schema:
        schema["required"] = [r for r in schema["required"] if r not in AUTH_PARAMS]

    return schema


async def get_mcp_tools(api_key: str | None = None) -> list[dict]:
    """
    Fetch available MCP tools from the server.
    Returns tools in OpenAI function calling format.
    Cached forever - restart bot to refresh.

    Note: api_key is not needed for tools/list (public), only for call_tool.
    """
    global _tools_cache

    if _tools_cache is not None:
        return _tools_cache

    # No auth needed for listing tools - OpenAPI schema is public
    transport = StreamableHttpTransport(MCP_URL)
    client = Client(transport)

    try:
        async with client:
            tools = await client.list_tools()

            # Convert MCP tools to OpenAI function format
            openai_tools = []
            for tool in tools:
                # Strip auth params - they're handled automatically by transport
                params = strip_auth_params(tool.inputSchema) if tool.inputSchema else {"type": "object", "properties": {}}

                openai_tool = {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description or "",
                        "parameters": params,
                    }
                }
                openai_tools.append(openai_tool)

            logger.info(f"Fetched and cached {len(openai_tools)} MCP tools")
            _tools_cache = openai_tools
            return openai_tools

    except Exception as e:
        logger.error(f"Failed to fetch MCP tools: {e}")
        return []


async def call_mcp_tool(api_key: str, tool_name: str, arguments: dict[str, Any]) -> str:
    """
    Call an MCP tool and return the result.
    """
    transport = StreamableHttpTransport(MCP_URL, auth=api_key)
    client = Client(transport)

    try:
        async with client:
            result = await client.call_tool(tool_name, arguments)

            # Extract text content from result
            if isinstance(result, str):
                return result
            elif hasattr(result, 'content'):
                # Handle MCP result format
                texts = []
                for content in result.content:
                    if hasattr(content, 'text'):
                        texts.append(content.text)
                return "\n".join(texts) if texts else str(result)
            else:
                return str(result)

    except Exception as e:
        logger.error(f"MCP tool call failed: {e}")
        return f"Error calling tool {tool_name}: {e}"


def format_tools_for_system_prompt(tools: list[dict]) -> str:
    """
    Format tools into a human-readable system prompt section.
    """
    if not tools:
        return ""

    lines = ["You have access to the following tools:\n"]
    for tool in tools:
        func = tool.get("function", {})
        name = func.get("name", "unknown")
        desc = func.get("description", "No description")
        lines.append(f"- **{name}**: {desc}")

    lines.append("\nTo use a tool, respond with a function call in your message.")
    return "\n".join(lines)
