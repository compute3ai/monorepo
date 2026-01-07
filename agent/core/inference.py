"""
Inference service - raw LLM calls with token streaming.

This module yields raw events for each token. No buffering or batching -
that's the transport layer's job.

Supports both OpenAI-style function calling and XML tool calls from models
like minimax that output their own format.
"""

import json
import logging
import re
from typing import AsyncIterator, Optional
from dataclasses import dataclass, field

from openai import AsyncOpenAI

from config import API_BASE_URL
from .mcp import get_mcp_tools, call_mcp_tool
from services.renders import create_render

logger = logging.getLogger(__name__)


def normalize_tool_name(name: str) -> str:
    """
    Normalize tool names from models that may mangle them.

    Handles both proper names (flow_image_to_image) and mangled ones (flowimagetoimage).
    """
    # If it already has underscores and looks valid, return as-is
    if "_" in name and name.startswith("flow_"):
        return name

    # Known tool name mappings (for models that remove underscores)
    mappings = {
        "flowimagetoimage": "flow_image_to_image",
        "flowimagetovideo": "flow_image_to_video",
        "flowtexttoimage": "flow_text_to_image",
        "flowtexttoimagehidream": "flow_text_to_image_hidream",
        "flowtexttovideo": "flow_text_to_video",
        "flowspeakingvideo": "flow_speaking_video",
        "flowspeakingvideowan": "flow_speaking_video_wan",
        "flowfirstlastframevideo": "flow_first_last_frame_video",
        "listrenders": "list_renders",
        "getrender": "get_render",
        "listjobs": "list_jobs",
        "getjob": "get_job",
        "createjob": "create_job",
    }
    return mappings.get(name.lower().replace("_", ""), name)


def normalize_argument_name(name: str) -> str:
    """
    Normalize argument names from models that may mangle them.

    Handles both proper names (image_url) and mangled ones (imageurl).
    """
    # If it already has underscores and looks like a known param, return as-is
    known_params = {"image_url", "image_urls", "audio_url", "notify_url",
                    "start_image_url", "end_image_url", "gpu_type", "gpu_count",
                    "docker_image", "env_vars", "prompt", "width", "height",
                    "file_ids"}
    if name in known_params:
        return name

    # Known argument name mappings (for models that remove underscores)
    mappings = {
        "imageurls": "image_urls",
        "imageurl": "image_url",
        "audiourl": "audio_url",
        "notifyurl": "notify_url",
        "startimageurl": "start_image_url",
        "endimageurl": "end_image_url",
        "gputype": "gpu_type",
        "gpucount": "gpu_count",
        "dockerimage": "docker_image",
        "envvars": "env_vars",
        "fileids": "file_ids",
    }
    return mappings.get(name.lower().replace("_", ""), name)


def normalize_argument_value(value: str):
    """
    Try to parse argument values as JSON if they look like arrays/objects.
    """
    value = value.strip()
    # Try to parse as JSON if it looks like an array or object
    if (value.startswith('[') and value.endswith(']')) or \
       (value.startswith('{') and value.endswith('}')):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass
    # Try to parse as number
    try:
        if '.' in value:
            return float(value)
        return int(value)
    except ValueError:
        pass
    return value


def extract_urls_from_messages(messages: list[dict]) -> dict:
    """
    Extract image/audio URLs and file_ids from message history.

    Supports formats:
    - [Image URL: https://...]  (legacy)
    - [Image: file_id=xxx url=https://...]  (new format with both)
    - [Audio URL: https://...]  (legacy)
    - [Audio: file_id=xxx url=https://...]  (new format with both)

    Returns dict with 'image_urls', 'image_file_ids', 'audio_url', 'audio_file_id' keys.
    """
    image_urls = []
    image_file_ids = []
    audio_url = None
    audio_file_id = None

    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            # New format: [Image: file_id=xxx url=https://...]
            for match in re.finditer(r'\[Image:\s*file_id=([^\s\]]+)\s+url=([^\]]+)\]', content):
                fid = match.group(1).strip()
                url = match.group(2).strip()
                if fid and fid not in image_file_ids:
                    image_file_ids.append(fid)
                if url and url not in image_urls:
                    image_urls.append(url)

            # Legacy format: [Image URL: https://...]
            for match in re.finditer(r'\[Image URL:\s*([^\]]+)\]', content):
                url = match.group(1).strip()
                if url and url not in image_urls:
                    image_urls.append(url)

            # New format: [Audio: file_id=xxx url=https://...]
            for match in re.finditer(r'\[Audio:\s*file_id=([^\s\]]+)\s+url=([^\]]+)\]', content):
                audio_file_id = match.group(1).strip()
                audio_url = match.group(2).strip()

            # Legacy format: [Audio URL: https://...]
            for match in re.finditer(r'\[Audio URL:\s*([^\]]+)\]', content):
                audio_url = match.group(1).strip()

    return {
        "image_urls": image_urls,
        "image_file_ids": image_file_ids,
        "audio_url": audio_url,
        "audio_file_id": audio_file_id,
    }


def inject_missing_urls(tool_name: str, arguments: dict, urls: dict) -> dict:
    """
    Inject missing URLs/file_ids into tool arguments if they weren't provided by the model.

    Prefers file_ids over URLs when available, as they're resolved reliably on the backend.
    """
    arguments = arguments.copy()

    image_file_ids = urls.get("image_file_ids", [])
    image_urls = urls.get("image_urls", [])
    audio_file_id = urls.get("audio_file_id")
    audio_url = urls.get("audio_url")

    # Tools that need image (single) - prefer file_ids
    if tool_name in ("flow_image_to_video", "flow_speaking_video"):
        if "file_ids" not in arguments and "image_url" not in arguments:
            if image_file_ids:
                arguments["file_ids"] = [image_file_ids[0]]
                logger.info(f"[URLS] Injected file_ids (image) for {tool_name}")
            elif image_urls:
                arguments["image_url"] = image_urls[0]
                logger.info(f"[URLS] Injected image_url for {tool_name}")

    # Tools that need image_urls (array) - prefer file_ids
    if tool_name == "flow_image_to_image":
        if "file_ids" not in arguments and "image_urls" not in arguments:
            if image_file_ids:
                arguments["file_ids"] = image_file_ids
                logger.info(f"[URLS] Injected file_ids (images) for {tool_name}")
            elif image_urls:
                arguments["image_urls"] = image_urls
                logger.info(f"[URLS] Injected image_urls for {tool_name}")

    # Tools that need audio - prefer file_id (appended to file_ids)
    if tool_name == "flow_speaking_video":
        if "audio_url" not in arguments:
            if audio_file_id:
                # For speaking_video, file_ids = [image_file_id, audio_file_id]
                if "file_ids" in arguments:
                    arguments["file_ids"].append(audio_file_id)
                elif image_file_ids:
                    arguments["file_ids"] = [image_file_ids[0], audio_file_id]
                    logger.info(f"[URLS] Injected file_ids (image+audio) for {tool_name}")
                else:
                    arguments["audio_url"] = audio_url
                    logger.info(f"[URLS] Injected audio_url for {tool_name}")
            elif audio_url:
                arguments["audio_url"] = audio_url
                logger.info(f"[URLS] Injected audio_url for {tool_name}")

    # Tools that need start/end image - prefer file_ids
    if tool_name == "flow_first_last_frame_video":
        if "file_ids" not in arguments and "start_image_url" not in arguments:
            if len(image_file_ids) >= 2:
                arguments["file_ids"] = image_file_ids[:2]
                logger.info(f"[URLS] Injected file_ids (start+end) for {tool_name}")
            elif len(image_file_ids) >= 1:
                arguments["file_ids"] = [image_file_ids[0]]
                logger.info(f"[URLS] Injected file_ids (start only) for {tool_name}")
            elif len(image_urls) >= 1:
                arguments["start_image_url"] = image_urls[0]
                logger.info(f"[URLS] Injected start_image_url for {tool_name}")
        if "file_ids" not in arguments and "end_image_url" not in arguments and len(image_urls) >= 2:
            arguments["end_image_url"] = image_urls[1]
            logger.info(f"[URLS] Injected end_image_url for {tool_name}")

    return arguments


def parse_xml_tool_calls(text: str) -> list[dict]:
    """
    Parse XML-style tool calls from model output.

    Supports multiple formats:

    1. Standard format (preferred):
    <tool_call>
    <invoke name="flow_text_to_image">
    <parameter name="prompt">a cat</parameter>
    </invoke>
    </tool_call>

    2. Minimax format (with or without underscore):
    <minimax:toolcall>
    <invoke name="flowtexttoimage">
    <prompt>a cat</prompt>
    </invoke>
    </minimax:toolcall>

    3. Direct child elements as parameters:
    <invoke name="tool_name">
    <prompt>value</prompt>
    <image_urls>["url1", "url2"]</image_urls>
    </invoke>

    4. Bare invoke tags with attributes:
    <invoke name="tool_name" arg1="value1"/>

    Returns list of {"name": str, "arguments": dict}
    """
    tool_calls = []

    # Find all invoke blocks (works inside any wrapper or standalone)
    invoke_patterns = [
        # Self-closing with attributes: <invoke name="x" a="1" b="2"/>
        r'<invoke\s+name=["\']([^"\']+)["\']([^>]*)/\s*>',
        # With children: <invoke name="x">...</invoke>
        r'<invoke\s+name=["\']([^"\']+)["\']([^>]*)>(.*?)</invoke>',
    ]

    for pattern in invoke_patterns:
        for match in re.finditer(pattern, text, re.DOTALL | re.IGNORECASE):
            tool_name = match.group(1)
            arguments = {}

            if len(match.groups()) == 2:
                # Self-closing tag - parse attributes
                attrs_str = match.group(2)
                # Parse attributes like: arg1="value1" arg2="value2"
                attr_pattern = r'(\w+)=["\']([^"\']*)["\']'
                for attr_match in re.finditer(attr_pattern, attrs_str):
                    key = normalize_argument_name(attr_match.group(1))
                    value = attr_match.group(2)
                    arguments[key] = normalize_argument_value(value)

            elif len(match.groups()) == 3:
                # Tag with children - first check for attributes on the tag
                attrs_str = match.group(2)
                content = match.group(3)

                # Parse attributes on the invoke tag itself
                attr_pattern = r'(\w+)=["\']([^"\']*)["\']'
                for attr_match in re.finditer(attr_pattern, attrs_str):
                    key = normalize_argument_name(attr_match.group(1))
                    value = attr_match.group(2)
                    arguments[key] = normalize_argument_value(value)

                # Parse <parameter name="x">value</parameter> children
                # Handle both single-line and multi-line parameter values
                param_pattern = r'<parameter\s+name=["\']([^"\']+)["\']>([\s\S]*?)</parameter>'
                for param_match in re.finditer(param_pattern, content, re.DOTALL):
                    key = normalize_argument_name(param_match.group(1))
                    value = param_match.group(2).strip()
                    arguments[key] = normalize_argument_value(value)

                # Also parse direct child elements as parameters (minimax format)
                # e.g., <prompt>value</prompt>, <imageurls>["url"]</imageurls>
                # Use lenient pattern that handles mismatched closing tags
                # (model sometimes outputs <image_urls>...</image> instead of </image_urls>)
                direct_param_pattern = r'<(\w+)>([\s\S]*?)</(\w+)>'
                for param_match in re.finditer(direct_param_pattern, content, re.DOTALL):
                    tag_name = param_match.group(1).lower()
                    # Skip if it's a wrapper tag or already handled
                    if tag_name in ('parameter', 'invoke', 'tool_call', 'toolcall'):
                        continue
                    key = normalize_argument_name(tag_name)
                    value = param_match.group(2).strip()
                    # Only add if not already set by <parameter> tags
                    if key not in arguments:
                        arguments[key] = normalize_argument_value(value)

            if tool_name:
                # Normalize tool name (handles both proper and mangled names)
                tool_calls.append({
                    "name": normalize_tool_name(tool_name),
                    "arguments": arguments,
                })

    return tool_calls


def strip_xml_tool_calls(text: str) -> str:
    """Remove XML tool call blocks from text to get clean response."""
    # Remove <tool_call>...</tool_call> blocks (standard format)
    text = re.sub(r'<tool_call>.*?</tool_call>', '', text, flags=re.DOTALL | re.IGNORECASE)
    # Remove <minimax:tool_call>...</minimax:tool_call> blocks (with underscore)
    text = re.sub(r'<minimax:tool_call>.*?</minimax:tool_call>', '', text, flags=re.DOTALL | re.IGNORECASE)
    # Remove <minimax:toolcall>...</minimax:toolcall> blocks (without underscore)
    text = re.sub(r'<minimax:toolcall>.*?</minimax:toolcall>', '', text, flags=re.DOTALL | re.IGNORECASE)
    # Remove standalone <invoke>...</invoke> blocks
    text = re.sub(r'<invoke\s+[^>]*>.*?</invoke>', '', text, flags=re.DOTALL | re.IGNORECASE)
    # Remove self-closing <invoke ... />
    text = re.sub(r'<invoke\s+[^>]*/>', '', text, flags=re.DOTALL | re.IGNORECASE)
    return text.strip()


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
    "flow_text_to_image": {
        "display_name": "Generate Image",
        "description": "Create image from text",
    },
    "flow_text_to_image_hidream": {
        "display_name": "Generate Image (HiDream)",
        "description": "Create high-quality image",
    },
    "flow_text_to_video": {
        "display_name": "Generate Video",
        "description": "Create video from text",
    },
    "flow_image_to_video": {
        "display_name": "Animate Image",
        "description": "Turn image into video",
    },
    "flow_image_to_image": {
        "display_name": "Edit Image",
        "description": "Transform/edit image",
    },
    "flow_speaking_video": {
        "display_name": "Speaking Video",
        "description": "Create lip-sync video",
    },
    "flow_first_last_frame_video": {
        "display_name": "Morph Video",
        "description": "Transition between images",
    },
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

        # If no OpenAI-style tool calls, check for XML tool calls in text
        if not tool_calls:
            xml_tool_calls = parse_xml_tool_calls(full_response)
            if xml_tool_calls:
                logger.info(f"[STREAM] Found {len(xml_tool_calls)} XML tool calls in response")
                # Execute XML tool calls
                tool_names = [tc["name"] for tc in xml_tool_calls]
                yield StreamEvent(type="tool_start", tool_name=", ".join(tool_names))

                # Extract URLs/file_ids from conversation history for fallback injection
                extracted_urls = extract_urls_from_messages(messages)
                if extracted_urls["image_urls"] or extracted_urls["image_file_ids"] or extracted_urls["audio_url"]:
                    logger.info(f"[URLS] Extracted from messages: {len(extracted_urls['image_file_ids'])} file_ids, {len(extracted_urls['image_urls'])} urls, audio={'yes' if extracted_urls['audio_url'] else 'no'}")

                # Check if confirmation is required
                if require_confirmation:
                    # Emit confirmation events for XML tool calls (same as OpenAI-style)
                    for i, tc in enumerate(xml_tool_calls):
                        tool_name = tc["name"]
                        arguments = tc["arguments"]
                        # Inject missing URLs from conversation history
                        arguments = inject_missing_urls(tool_name, arguments, extracted_urls)

                        yield StreamEvent(
                            type="tool_confirmation",
                            tool_name=tool_name,
                            tool_args=arguments,
                            tool_call_id=f"xml_{i}",
                            content=json.dumps({
                                "display_name": tool_name.replace("_", " ").title(),
                                "description": "",
                                "options": [
                                    {"id": "proceed", "label": "✓ Run"},
                                    {"id": "cancel", "label": "✗ Cancel"},
                                ],
                            }),
                        )

                    # Strip XML from response for cleaner display
                    clean_response = strip_xml_tool_calls(full_response)
                    yield StreamEvent(type="done", content=clean_response or "")
                    return

                # Execute immediately (no confirmation required)
                tool_results = []
                for tc in xml_tool_calls:
                    tool_name = tc["name"]
                    arguments = tc["arguments"]
                    # Inject missing URLs from conversation history
                    arguments = inject_missing_urls(tool_name, arguments, extracted_urls)
                    logger.info(f"[STREAM] Executing XML tool call: {tool_name} with args: {arguments}")

                    result = await call_mcp_tool(api_key, tool_name, arguments, notify_url=notify_url)
                    _track_render_creation(user_id, chat_id, tool_name, arguments, result)

                    yield StreamEvent(
                        type="tool_result",
                        tool_name=tool_name,
                        tool_args=arguments,
                        tool_result=result,
                    )
                    tool_results.append({"tool": tool_name, "result": result})

                # Strip XML from response and append tool results summary
                clean_response = strip_xml_tool_calls(full_response)
                if tool_results:
                    # Build a summary of tool results
                    result_lines = []
                    for tr in tool_results:
                        tool = tr['tool']
                        result = tr['result'] or "(no result)"
                        # Truncate long results
                        if len(result) > 500:
                            result = result[:500] + "..."
                        result_lines.append(f"✅ {tool}: {result}")

                    results_text = "\n\n".join(result_lines)
                    if clean_response:
                        final_response = f"{clean_response}\n\n{results_text}"
                    else:
                        final_response = results_text
                else:
                    final_response = clean_response or full_response

                # Ensure we never return an empty response
                if not final_response or not final_response.strip():
                    final_response = "✅ Request submitted. You'll receive the result when it's ready."

                logger.info(f"[STREAM] XML tool calls done, final_response length: {len(final_response)}")
                yield StreamEvent(type="done", content=final_response)
                return

            # No tool calls at all
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

        # Debug log full response and tool calls
        logger.debug(f"[STREAM] Full response text: {full_response}")
        for tc_id, tc in tool_calls.items():
            logger.debug(f"[STREAM] Accumulated tool call {tc_id}: name={tc['name']} args={tc['arguments']}")

        assistant_message = MockMessage(
            content=full_response,
            tool_calls=[MockToolCall(id, tc["name"], tc["arguments"]) for id, tc in tool_calls.items()]
        )

        if assistant_message.tool_calls:
            tool_names = [tc.function.name for tc in assistant_message.tool_calls]
            yield StreamEvent(type="tool_start", tool_name=", ".join(tool_names))

            # Extract URLs/file_ids from conversation history for fallback injection
            extracted_urls = extract_urls_from_messages(messages)
            if extracted_urls["image_urls"] or extracted_urls["image_file_ids"] or extracted_urls["audio_url"]:
                logger.info(f"[URLS] Extracted from messages: {len(extracted_urls['image_file_ids'])} file_ids, {len(extracted_urls['image_urls'])} urls, audio={'yes' if extracted_urls['audio_url'] else 'no'}")
                logger.debug(f"[URLS] Image file_ids: {extracted_urls['image_file_ids']}")
                logger.debug(f"[URLS] Image URLs: {extracted_urls['image_urls']}")
                logger.debug(f"[URLS] Audio file_id: {extracted_urls['audio_file_id']}, URL: {extracted_urls['audio_url']}")

            # Check if any tool requires confirmation
            pending_confirmations = []
            tools_to_execute = []

            for tool_call in assistant_message.tool_calls:
                tool_name = tool_call.function.name
                raw_args = tool_call.function.arguments
                logger.debug(f"[STREAM] Raw tool call: {tool_name} args={raw_args}")
                try:
                    arguments = json.loads(raw_args)
                except json.JSONDecodeError:
                    # Log the malformed arguments for debugging
                    logger.error(f"[STREAM] Failed to parse tool arguments as JSON: {raw_args}")

                    # Try to salvage: if it's raw text, treat it as the prompt
                    if raw_args and raw_args.strip() and tool_name.startswith("flow_"):
                        logger.info(f"[STREAM] Attempting to use raw text as prompt for {tool_name}")
                        arguments = {"prompt": raw_args.strip()}
                    else:
                        arguments = {}

                # Normalize argument names and values (handle double-encoded JSON, mangled names)
                normalized_args = {}
                for key, value in arguments.items():
                    norm_key = normalize_argument_name(key)
                    if isinstance(value, str):
                        norm_value = normalize_argument_value(value)
                    else:
                        norm_value = value
                    normalized_args[norm_key] = norm_value
                arguments = normalized_args

                # Inject missing URLs from conversation history
                arguments = inject_missing_urls(tool_name, arguments, extracted_urls)

                if require_confirmation:
                    # All tools need user confirmation
                    pending_confirmations.append({
                        "tool_call_id": tool_call.id,
                        "tool_name": tool_name,
                        "arguments": arguments,
                        "display_name": tool_name.replace("_", " ").title(),
                        "description": "",
                        "options": [
                            {"id": "proceed", "label": "✓ Run"},
                            {"id": "cancel", "label": "✗ Cancel"},
                        ],
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
                logger.info(f"[STREAM] Executing OpenAI tool call: {tool_name} with args: {arguments}")

                # Validate we have required arguments before calling
                if not arguments:
                    logger.error(f"[STREAM] No arguments for tool {tool_name}, skipping")
                    result = f"Error: No arguments provided for {tool_name}"
                else:
                    result = await call_mcp_tool(api_key, tool_name, arguments, notify_url=notify_url)
                logger.info(f"[STREAM] Tool result: {result[:200] if result else '(empty)'}...")
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

            # Get final response from LLM (buffered, not streamed, to allow XML stripping)
            logger.info(f"[STREAM] Making second LLM call for final response")
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                stream=False,
            )

            full_response = response.choices[0].message.content or ""

            # Strip any XML tool calls from the response
            full_response = strip_xml_tool_calls(full_response)

            # Fallback if empty after stripping
            if not full_response or not full_response.strip():
                full_response = "✅ Request submitted. You'll receive the result when it's ready."

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
