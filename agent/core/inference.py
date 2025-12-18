"""
Inference service - raw LLM calls with token streaming.

This module yields raw events for each token. No buffering or batching -
that's the transport layer's job.
"""

import json
import logging
from typing import AsyncIterator, Optional
from dataclasses import dataclass, field

from openai import AsyncOpenAI

from config import API_BASE_URL
from .mcp import get_mcp_tools, call_mcp_tool
from services.renders import create_render

logger = logging.getLogger(__name__)


@dataclass
class StreamEvent:
    """Event from the inference stream.

    Event types:
    - token: New token received (content has the full accumulated text)
    - tool_start: Starting tool execution (tool_name set)
    - tool_result: Tool completed (tool_result set)
    - tool_confirmation: Tool requires user confirmation before execution
    - error: Error occurred (content has error message)
    - done: Stream complete (content has final text)
    """
    type: str
    content: str = ""
    tool_name: str = ""
    tool_args: dict = field(default_factory=dict)
    tool_result: str = ""
    tool_call_id: str = ""  # For tracking tool calls needing confirmation


# Tools that require user confirmation before execution
TOOLS_REQUIRING_CONFIRMATION = {
    "create_render": {
        "display_name": "Create Render",
        "description": "Generate an image or video",
        "option_generator": "_generate_render_options",
    },
    # Add more tools here as needed
}


def _generate_render_options(tool_args: dict) -> list[dict]:
    """Generate selection options for render creation.

    Returns options like:
    - Proceed with selected template
    - Try a different template
    - Cancel
    """
    params = tool_args.get("params", {})
    template = params.get("template", "unknown")
    prompt = params.get("prompt", "")[:50]

    return [
        {
            "id": "proceed",
            "label": f"Create with {template}",
            "description": f'"{prompt}..."' if len(prompt) > 0 else None,
        },
        {
            "id": "cancel",
            "label": "Cancel",
        },
    ]


def _track_render_creation(
    user_id: Optional[str],
    chat_id: Optional[str],
    tool_name: str,
    arguments: dict,
    result: str,
) -> None:
    """Track render creation in the database when create_render tool is called."""
    if tool_name != "create_render":
        return
    if not user_id or not chat_id:
        logger.warning("Cannot track render: missing user_id or chat_id")
        return

    try:
        result_data = json.loads(result)
        render_id = result_data.get("id") or result_data.get("render_id")
        if not render_id:
            logger.warning(f"No render_id in result: {result}")
            return

        params = arguments.get("params", {})
        prompt = params.get("prompt")
        template = params.get("template")

        create_render(
            user_id=user_id,
            chat_id=chat_id,
            render_id=render_id,
            prompt=prompt,
            template=template,
        )
        logger.info(f"Tracked render creation: {render_id} for user {user_id}")

    except json.JSONDecodeError:
        logger.warning(f"Failed to parse tool result as JSON: {result}")
    except Exception as e:
        logger.error(f"Failed to track render creation: {e}")


async def stream_completion(
    api_key: str,
    model: str,
    messages: list[dict],
    use_tools: bool = True,
    user_id: Optional[str] = None,
    chat_id: Optional[str] = None,
    require_confirmation: bool = False,
    notify_url: Optional[str] = None,
) -> AsyncIterator[StreamEvent]:
    """
    Stream chat completion, yielding events for each token and tool call.

    This is a RAW stream - no buffering. Each token is yielded immediately.
    The transport layer decides how to batch/buffer for its output.

    Args:
        api_key: API key for the LLM service
        model: Model to use
        messages: Conversation history
        use_tools: Whether to enable tool use
        user_id: User ID for tracking
        chat_id: Chat ID for tracking
        require_confirmation: If True, tools in TOOLS_REQUIRING_CONFIRMATION
            will emit tool_confirmation events instead of executing immediately
        notify_url: Webhook URL for render completion notifications (injected into flow_* tools)

    Yields:
        StreamEvent objects with type:
        - "token": New token received (content has the full accumulated text)
        - "tool_start": Starting tool execution (tool_name set)
        - "tool_result": Tool completed (tool_result set)
        - "tool_confirmation": Tool requires user confirmation (when require_confirmation=True)
        - "error": Error occurred (content has error message)
        - "done": Stream complete (content has final text)
    """
    client = AsyncOpenAI(
        api_key=api_key,
        base_url=f"{API_BASE_URL}/v1",
        default_headers={"User-Agent": "compute3-agent/0.1"},
    )

    # Fetch MCP tools
    tools = None
    if use_tools:
        try:
            tools = await get_mcp_tools(api_key)
            if not tools:
                tools = None
        except Exception as e:
            logger.warning(f"Failed to fetch MCP tools: {e}")

    messages = messages.copy()

    try:
        # Stream with tools - accumulate content and tool calls
        try:
            logger.info(f"[STREAM] Starting streaming call to {model} with tools={tools is not None}")
            stream = await client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools if tools else None,
                stream=True,
            )
            logger.info(f"[STREAM] Stream created, starting iteration")
        except Exception as tool_err:
            err_str = str(tool_err).lower()
            tool_unsupported = (
                "tool use" in err_str or
                "tool_use" in err_str or
                "function calling" in err_str or
                "no endpoints found" in err_str
            )
            if tool_unsupported:
                logger.warning(f"Model {model} doesn't support tools, falling back")
                tools = None
                stream = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    stream=True,
                )
            else:
                raise

        # Accumulate streaming response
        full_response = ""
        tool_calls = {}  # id -> {name, arguments}
        first_token_logged = False

        async for chunk in stream:
            if not first_token_logged:
                logger.info(f"[STREAM] First chunk received")
                first_token_logged = True
            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta

            # Stream content immediately
            if delta.content:
                full_response += delta.content
                if len(full_response) <= 50:  # Log first 50 chars worth of token events
                    logger.info(f"[STREAM] Token yielded, total_len={len(full_response)}")
                yield StreamEvent(type="token", content=full_response)

            # Accumulate tool calls
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    tc_id = tc.id or list(tool_calls.keys())[-1] if tool_calls else "0"
                    if tc.id:
                        tool_calls[tc.id] = {"name": tc.function.name or "", "arguments": ""}
                    if tc.function and tc.function.arguments:
                        if tc_id in tool_calls:
                            tool_calls[tc_id]["arguments"] += tc.function.arguments

        # If no tool calls, we're done
        if not tool_calls:
            logger.info(f"[STREAM] No tool calls, yielding done event with {len(full_response)} chars")
            yield StreamEvent(type="done", content=full_response)
            return

        # Build assistant message for tool handling
        class MockToolCall:
            def __init__(self, id, name, args):
                self.id = id
                self.function = type('obj', (object,), {'name': name, 'arguments': args})()

        class MockMessage:
            def __init__(self, content, tool_calls):
                self.content = content
                self.tool_calls = tool_calls

        assistant_message = MockMessage(
            content=full_response,
            tool_calls=[MockToolCall(id, tc["name"], tc["arguments"]) for id, tc in tool_calls.items()]
        )

        if assistant_message.tool_calls:
            tool_names = [tc.function.name for tc in assistant_message.tool_calls]
            yield StreamEvent(type="tool_start", tool_name=", ".join(tool_names))

            # Check if any tool requires confirmation
            pending_confirmations = []
            tools_to_execute = []

            for tool_call in assistant_message.tool_calls:
                tool_name = tool_call.function.name
                try:
                    arguments = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    arguments = {}

                if require_confirmation and tool_name in TOOLS_REQUIRING_CONFIRMATION:
                    # This tool needs user confirmation
                    config = TOOLS_REQUIRING_CONFIRMATION[tool_name]
                    option_generator = globals().get(config.get("option_generator"))
                    options = option_generator(arguments) if option_generator else [
                        {"id": "proceed", "label": "Proceed"},
                        {"id": "cancel", "label": "Cancel"},
                    ]

                    pending_confirmations.append({
                        "tool_call_id": tool_call.id,
                        "tool_name": tool_name,
                        "arguments": arguments,
                        "display_name": config.get("display_name", tool_name),
                        "description": config.get("description", ""),
                        "options": options,
                    })
                else:
                    tools_to_execute.append((tool_call, tool_name, arguments))

            # If there are tools requiring confirmation, emit event and pause
            if pending_confirmations:
                # Emit confirmation event with all pending tool calls
                for pending in pending_confirmations:
                    yield StreamEvent(
                        type="tool_confirmation",
                        tool_name=pending["tool_name"],
                        tool_args=pending["arguments"],
                        tool_call_id=pending["tool_call_id"],
                        content=json.dumps({
                            "display_name": pending["display_name"],
                            "description": pending["description"],
                            "options": pending["options"],
                        }),
                    )
                # Don't continue - let the frontend handle the confirmation
                # and call execute_confirmed_tool when user responds
                return

            # Add assistant message to history
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

            # Execute tools that don't need confirmation
            for tool_call, tool_name, arguments in tools_to_execute:
                result = await call_mcp_tool(api_key, tool_name, arguments, notify_url=notify_url)
                _track_render_creation(user_id, chat_id, tool_name, arguments, result)

                yield StreamEvent(
                    type="tool_result",
                    tool_name=tool_name,
                    tool_args=arguments,
                    tool_result=result,
                )

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })

            # Get final response (no tools to prevent loops)
            stream = await client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True,
            )

            full_response = ""
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    yield StreamEvent(type="token", content=full_response)

            yield StreamEvent(type="done", content=full_response)

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Inference error: {e}")
        yield StreamEvent(type="error", content=error_msg)


async def execute_confirmed_tool(
    api_key: str,
    tool_name: str,
    tool_args: dict,
    user_id: Optional[str] = None,
    chat_id: Optional[str] = None,
    notify_url: Optional[str] = None,
) -> AsyncIterator[StreamEvent]:
    """
    Execute a tool that was confirmed by the user.

    This is called after the user confirms a tool_confirmation event.
    It executes the tool and yields the result.

    Args:
        api_key: API key for the MCP service
        tool_name: Name of the tool to execute
        tool_args: Arguments for the tool
        user_id: User ID for tracking
        chat_id: Chat ID for tracking
        notify_url: Webhook URL for render completion notifications

    Yields:
        StreamEvent with tool_result type
    """
    try:
        result = await call_mcp_tool(api_key, tool_name, tool_args, notify_url=notify_url)
        _track_render_creation(user_id, chat_id, tool_name, tool_args, result)

        yield StreamEvent(
            type="tool_result",
            tool_name=tool_name,
            tool_args=tool_args,
            tool_result=result,
        )
        yield StreamEvent(type="done", content=result)

    except Exception as e:
        logger.error(f"Tool execution error: {e}")
        yield StreamEvent(type="error", content=str(e))


async def complete(api_key: str, model: str, message: str) -> str:
    """Simple non-streaming completion for one-off requests."""
    client = AsyncOpenAI(
        api_key=api_key,
        base_url=f"{API_BASE_URL}/v1",
        default_headers={"User-Agent": "compute3-agent/0.1"},
    )

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": message}],
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        return f"Error: {str(e)}"
