"""
Inference service - OpenAI-compatible chat completions with streaming and MCP tool support.
"""

import json
import logging
from typing import Callable, Awaitable
from openai import AsyncOpenAI
from config import API_BASE_URL
from services.mcp import get_mcp_tools, call_mcp_tool

logger = logging.getLogger(__name__)

# Punctuation that triggers a flush
FLUSH_CHARS = {'.', ',', ':', ';', '!', '?', '*', '\n'}

# Max tool call iterations to prevent infinite loops
MAX_TOOL_ITERATIONS = 10


async def chat_completion_stream(
    api_key: str,
    model: str,
    messages: list[dict],
    on_update: Callable[[str], Awaitable[None]],
    use_tools: bool = True,
) -> str:
    """
    Stream chat completion with punctuation-based updates and MCP tool support.

    Args:
        api_key: User's API key
        model: Model to use
        messages: Conversation history as list of {"role": "user/assistant", "content": "..."}
        on_update: Async callback called with accumulated text on each flush
        use_tools: Whether to enable MCP tools (default: True)

    Returns:
        Final complete response text.
    """
    logger.info(f"chat_completion_stream called with model={model} messages={len(messages)} use_tools={use_tools}")

    client = AsyncOpenAI(
        api_key=api_key,
        base_url=f"{API_BASE_URL}/v1",
        default_headers={"User-Agent": "c3-tgbot/0.1"},
    )

    # Fetch MCP tools if enabled
    tools = None
    if use_tools:
        try:
            tools = await get_mcp_tools(api_key)
            if tools:
                logger.info(f"Loaded {len(tools)} MCP tools")
            else:
                tools = None
        except Exception as e:
            logger.warning(f"Failed to fetch MCP tools: {e}")
            tools = None

    # Make a copy of messages for tool call loop (don't modify original)
    messages = messages.copy()

    # Tool calling loop
    for iteration in range(MAX_TOOL_ITERATIONS):
        try:
            # Make API call (non-streaming if tools might be called, streaming for final response)
            if tools and iteration < MAX_TOOL_ITERATIONS - 1:
                # Non-streaming call to check for tool use
                response = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    tools=tools,
                )
                assistant_message = response.choices[0].message

                # Check if model wants to call tools
                if assistant_message.tool_calls:
                    logger.info(f"Model requested {len(assistant_message.tool_calls)} tool calls")

                    # Show tool calling status
                    tool_names = [tc.function.name for tc in assistant_message.tool_calls]
                    await on_update(f"🔧 Calling tools: {', '.join(tool_names)}...")

                    # Add assistant message with tool calls
                    messages.append({
                        "role": "assistant",
                        "content": assistant_message.content,
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                }
                            }
                            for tc in assistant_message.tool_calls
                        ]
                    })

                    # Execute each tool call
                    for tool_call in assistant_message.tool_calls:
                        tool_name = tool_call.function.name
                        try:
                            arguments = json.loads(tool_call.function.arguments)
                        except json.JSONDecodeError:
                            arguments = {}

                        logger.info(f"Calling MCP tool: {tool_name} with {arguments}")
                        result = await call_mcp_tool(api_key, tool_name, arguments)

                        # Add tool result to messages
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": result,
                        })

                    # Continue loop to get next response
                    continue

                # No tool calls - simulate streaming by flushing at punctuation
                final_response = assistant_message.content or ""
                accumulated = ""
                for char in final_response:
                    accumulated += char
                    if char in FLUSH_CHARS:
                        await on_update(accumulated)
                # Final update with full response
                await on_update(final_response)
                return final_response

            else:
                # Stream the final response (no more tool calls expected)
                stream = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    stream=True,
                )

                full_response = ""
                buffer = ""

                async for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        full_response += content
                        buffer += content

                        # Check if buffer ends with flush character
                        if buffer and buffer[-1] in FLUSH_CHARS:
                            await on_update(full_response)
                            buffer = ""

                # Final flush if anything remaining
                if buffer:
                    await on_update(full_response)

                return full_response

        except Exception as e:
            error_msg = f"❌ Error: {str(e)}"
            await on_update(error_msg)
            return error_msg

    # Shouldn't reach here, but just in case
    return "❌ Error: Too many tool iterations"


async def chat_completion(api_key: str, model: str, message: str) -> str:
    """
    Run chat completion (non-streaming fallback).
    Returns the assistant's response text.
    """
    logger.info(f"chat_completion called with model={model}")

    client = AsyncOpenAI(
        api_key=api_key,
        base_url=f"{API_BASE_URL}/v1",
        default_headers={"User-Agent": "c3-tgbot/0.1"},
    )

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": message}],
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        return f"❌ Error: {str(e)}"
