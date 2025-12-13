"""
Inference service - OpenAI-compatible chat completions with streaming and MCP tool support.
"""

import json
import logging
from typing import Callable, Awaitable, Optional
from openai import AsyncOpenAI
from config import API_BASE_URL
from services.mcp import get_mcp_tools, call_mcp_tool
from renders import create_render

logger = logging.getLogger(__name__)


def _track_render_creation(
    user_id: Optional[str],
    thread_id: Optional[str],
    tool_name: str,
    arguments: dict,
    result: str,
) -> None:
    """Track render creation in the database when create_render tool is called."""
    if tool_name != "create_render":
        return
    if not user_id or not thread_id:
        logger.warning("Cannot track render: missing user_id or thread_id")
        return

    try:
        # Parse result to get render_id
        result_data = json.loads(result)
        render_id = result_data.get("id") or result_data.get("render_id")
        if not render_id:
            logger.warning(f"No render_id in result: {result}")
            return

        # Extract prompt and template from arguments
        params = arguments.get("params", {})
        prompt = params.get("prompt")
        template = params.get("template")

        # Create render tracking record
        create_render(
            user_id=user_id,
            thread_id=thread_id,
            render_id=render_id,
            prompt=prompt,
            template=template,
        )
        logger.info(f"Tracked render creation: {render_id} for user {user_id}")

    except json.JSONDecodeError:
        logger.warning(f"Failed to parse tool result as JSON: {result}")
    except Exception as e:
        logger.error(f"Failed to track render creation: {e}")

# Punctuation that triggers a flush
FLUSH_CHARS = {'.', ',', ':', ';', '!', '?', '*', '\n'}


async def chat_completion_stream(
    api_key: str,
    model: str,
    messages: list[dict],
    on_update: Callable[[str], Awaitable[None]],
    use_tools: bool = True,
    user_id: Optional[str] = None,
    thread_id: Optional[str] = None,
) -> str:
    """
    Stream chat completion with punctuation-based updates and MCP tool support.

    Args:
        api_key: User's API key
        model: Model to use
        messages: Conversation history as list of {"role": "user/assistant", "content": "..."}
        on_update: Async callback called with accumulated text on each flush
        use_tools: Whether to enable MCP tools (default: True)
        user_id: User ID for tracking render creation
        thread_id: Thread ID for tracking render creation

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

    # Make a copy of messages (don't modify original)
    messages = messages.copy()

    try:
        # STEP 1: Make initial call with tools (if available)
        if tools:
            logger.info(f"Making initial call with {len(tools)} tools available")
            try:
                response = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    tools=tools,
                )
            except Exception as tool_err:
                # Check if this is a "tool use not supported" error
                err_str = str(tool_err).lower()
                tool_unsupported = (
                    "tool use" in err_str or
                    "tool_use" in err_str or
                    "function calling" in err_str or
                    "no endpoints found" in err_str
                )
                if tool_unsupported:
                    logger.warning(f"Model {model} doesn't support tools, falling back to no-tools")
                    tools = None  # Disable tools
                else:
                    raise  # Re-raise other errors

        # If no tools or tools disabled, make a streaming call
        if not tools:
            logger.info("Streaming response without tools")
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

        # STEP 2: Check if model called tools
        assistant_message = response.choices[0].message

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

                # Track render creation if applicable
                _track_render_creation(user_id, thread_id, tool_name, arguments, result)

                # Add tool result to messages
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })

            # STEP 3: Get ONE final summary response (WITHOUT tools to prevent loops)
            logger.info("Getting final summary response (tools disabled)")
            stream = await client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True,
                # NO TOOLS - prevents infinite loops
            )

            full_response = ""
            buffer = ""
            chunk_count = 0

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    buffer += content
                    chunk_count += 1

                    # Flush on punctuation OR every 10 chunks (whichever comes first)
                    should_flush = (buffer and buffer[-1] in FLUSH_CHARS) or (chunk_count >= 10)

                    if should_flush:
                        await on_update(full_response)
                        buffer = ""
                        chunk_count = 0

            # Final flush if anything remaining
            if buffer or full_response:
                await on_update(full_response)

            logger.info("Summary complete - ONE message cycle done")
            return full_response

        else:
            # No tool calls - return the text response directly
            final_response = assistant_message.content or ""
            logger.info("No tool calls - returning direct response")

            # Simulate streaming by flushing at punctuation
            accumulated = ""
            for char in final_response:
                accumulated += char
                if char in FLUSH_CHARS:
                    await on_update(accumulated)
            await on_update(final_response)
            return final_response

    except Exception as e:
        error_msg = f"❌ Error: {str(e)}"
        logger.error(f"Chat completion error: {e}")
        await on_update(error_msg)
        return error_msg


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
