"""
Chat API routes - REST + WebSocket.

Architecture:
- POST /chats/{chat_id}/messages: Send message, returns immediately, kicks off async inference
- WS /chats/{chat_id}/stream: Subscribe to live tokens, reconnect anytime
- GET /chats/{chat_id}/messages: Get all messages (including partial if streaming)
"""

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from frontends.web.dependencies import require_api_key, require_auth, AuthInfo, JWT_VERIFY, PUBLIC_KEY
import jwt
from frontends.web.state import active_streams
from services import chats, users
from core import stream_completion
from core.prompts import build_system_prompt
from config import DEFAULT_MODEL, API_BASE_URL, URL_PREFIX


def get_notify_url(webhook_secret: str) -> str | None:
    """Construct the render notification webhook URL for a user."""
    if not API_BASE_URL:
        return None
    return f"{API_BASE_URL}{URL_PREFIX}/api/render/{webhook_secret}"

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chats", tags=["chats"])


# =============================================================================
# Pydantic models
# =============================================================================


class ChatCreate(BaseModel):
    title: Optional[str] = None


class ChatResponse(BaseModel):
    id: str
    title: Optional[str]
    created_at: str
    updated_at: str


class MessageCreate(BaseModel):
    content: str
    model: Optional[str] = None  # Override user's default model


class MessageResponse(BaseModel):
    id: int
    role: str
    content: str
    type: str = "text"  # text, selection, selection_response
    meta: Optional[dict] = None  # selection options, tool call data, etc.
    status: str
    error: Optional[str]
    created_at: str


class SendMessageResponse(BaseModel):
    user_message_id: int
    assistant_message_id: int
    status: str  # "processing"


# =============================================================================
# Helper functions
# =============================================================================


async def run_inference(
    user_id: str,
    chat_id: str,
    message_id: int,
    api_key: str,
    model: str,
    messages: list[dict],
    require_confirmation: bool = True,
    notify_url: str | None = None,
):
    """
    Run inference in background and update message status.
    Broadcasts tokens to WebSocket subscribers.

    Args:
        require_confirmation: If True, tools in TOOLS_REQUIRING_CONFIRMATION
            will create selection messages for user confirmation.
        notify_url: Webhook URL for render completion notifications.
    """
    import json as json_module

    # Update stream state (already initialized in POST endpoint)
    if message_id not in active_streams:
        active_streams[message_id] = {
            "content": "",
            "status": "streaming",
            "subscribers": set(),
        }
    else:
        active_streams[message_id]["status"] = "streaming"

    try:
        # Update status to streaming
        chats.update_message_status(message_id, "streaming")

        final_content = ""

        async for event in stream_completion(
            api_key=api_key,
            model=model,
            messages=messages,
            user_id=user_id,
            chat_id=chat_id,
            require_confirmation=require_confirmation,
            notify_url=notify_url,
        ):
            if event.type == "token":
                final_content = event.content
                active_streams[message_id]["content"] = final_content

                # Broadcast to subscribers
                subs = active_streams[message_id]["subscribers"]
                logger.info(f"[WS] Token event, {len(subs)} subscribers, content_len={len(final_content)}")
                for queue in subs:
                    await queue.put({"type": "token", "content": final_content})

                # Periodically save to DB (every ~500 chars)
                if len(final_content) % 500 < 10:
                    chats.update_message_content(message_id, final_content)

            elif event.type == "tool_start":
                for queue in active_streams[message_id]["subscribers"]:
                    await queue.put({"type": "tool_start", "tools": event.tool_name})

            elif event.type == "tool_result":
                for queue in active_streams[message_id]["subscribers"]:
                    await queue.put({
                        "type": "tool_result",
                        "tool": event.tool_name,
                        "result": event.tool_result,
                    })

            elif event.type == "tool_confirmation":
                # Tool requires user confirmation - create a selection message
                try:
                    confirmation_data = json_module.loads(event.content)
                except json_module.JSONDecodeError:
                    confirmation_data = {}

                display_name = confirmation_data.get("display_name", event.tool_name)
                options = confirmation_data.get("options", [
                    {"id": "proceed", "label": "Proceed"},
                    {"id": "cancel", "label": "Cancel"},
                ])

                # Update the current message as a selection
                # Store the tool call info so we can execute it after confirmation
                tool_call_data = {
                    "id": event.tool_call_id,
                    "name": event.tool_name,
                    "arguments": event.tool_args,
                }

                # Delete the pending assistant message and create a selection message
                chats.update_message_status(message_id, "complete", content="")

                selection_content = f"Ready to {display_name.lower()}. Please confirm:"
                selection_msg = chats.create_selection_message(
                    user_id=user_id,
                    chat_id=chat_id,
                    content=selection_content,
                    options=options,
                    tool_call=tool_call_data,
                )

                # Broadcast the selection to subscribers
                active_streams[message_id]["status"] = "selection"
                for queue in active_streams[message_id]["subscribers"]:
                    await queue.put({
                        "type": "selection",
                        "message_id": selection_msg.id,
                        "content": selection_content,
                        "options": options,
                    })

                # Don't continue - wait for user selection
                return

            elif event.type == "done":
                final_content = event.content
                chats.update_message_status(message_id, "complete", content=final_content)
                active_streams[message_id]["status"] = "complete"
                active_streams[message_id]["content"] = final_content

                for queue in active_streams[message_id]["subscribers"]:
                    await queue.put({"type": "done", "content": final_content})

            elif event.type == "error":
                chats.update_message_status(message_id, "error", error=event.content)
                active_streams[message_id]["status"] = "error"

                for queue in active_streams[message_id]["subscribers"]:
                    await queue.put({"type": "error", "error": event.content})

    except Exception as e:
        logger.error(f"Inference error: {e}")
        chats.update_message_status(message_id, "error", error=str(e))
        active_streams[message_id]["status"] = "error"

        for queue in active_streams[message_id]["subscribers"]:
            await queue.put({"type": "error", "error": str(e)})

    finally:
        # Clean up after a delay (allow reconnects)
        await asyncio.sleep(60)
        if message_id in active_streams:
            del active_streams[message_id]


# =============================================================================
# REST endpoints
# =============================================================================


@router.post("", response_model=ChatResponse)
async def create_chat(
    data: ChatCreate,
    user_id: str = Depends(require_api_key),
):
    """Create a new chat."""
    chat = chats.create_chat(user_id, data.title)
    return ChatResponse(
        id=chat.id,
        title=chat.title,
        created_at=chat.created_at.isoformat(),
        updated_at=chat.updated_at.isoformat(),
    )


@router.get("", response_model=list[ChatResponse])
async def list_chats(
    limit: int = 20,
    user_id: str = Depends(require_api_key),
):
    """List user's chats."""
    chat_list = chats.get_user_chats(user_id, limit)
    return [
        ChatResponse(
            id=c.id,
            title=c.title,
            created_at=c.created_at.isoformat(),
            updated_at=c.updated_at.isoformat(),
        )
        for c in chat_list
    ]


@router.get("/{chat_id}", response_model=ChatResponse)
async def get_chat(
    chat_id: str,
    user_id: str = Depends(require_api_key),
):
    """Get a chat by ID."""
    chat = chats.get_chat(chat_id)
    if not chat or chat.user_id != user_id:
        raise HTTPException(status_code=404, detail="Chat not found")

    return ChatResponse(
        id=chat.id,
        title=chat.title,
        created_at=chat.created_at.isoformat(),
        updated_at=chat.updated_at.isoformat(),
    )


@router.delete("/{chat_id}")
async def delete_chat(
    chat_id: str,
    user_id: str = Depends(require_api_key),
):
    """Delete a chat."""
    success = chats.delete_chat(chat_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Chat not found")
    return {"status": "deleted"}


@router.get("/{chat_id}/messages", response_model=list[MessageResponse])
async def get_messages(
    chat_id: str,
    user_id: str = Depends(require_api_key),
):
    """Get all messages in a chat."""
    chat = chats.get_chat(chat_id)
    if not chat or chat.user_id != user_id:
        raise HTTPException(status_code=404, detail="Chat not found")

    messages = chats.get_messages(chat_id)
    return [
        MessageResponse(
            id=m["id"],
            role=m["role"],
            content=m["content"],
            type=m.get("type", "text"),
            meta=m.get("meta"),
            status=m["status"],
            error=m.get("error"),
            created_at=m["created_at"],
        )
        for m in messages
    ]


@router.post("/{chat_id}/messages", response_model=SendMessageResponse)
async def send_message(
    chat_id: str,
    data: MessageCreate,
    auth: AuthInfo = Depends(require_auth),
):
    """
    Send a message and start AI response generation.

    Returns immediately with message IDs. The assistant response will be
    generated in the background. Connect to the WebSocket endpoint to
    receive streaming tokens.
    """
    user_id = auth.user_id

    # Verify chat exists and belongs to user
    chat = chats.get_chat(chat_id)
    if not chat or chat.user_id != user_id:
        raise HTTPException(status_code=404, detail="Chat not found")

    # Get user for model preference
    user = users.get_user(user_id)

    # Store user message
    user_msg = chats.add_message(
        user_id=user_id,
        chat_id=chat_id,
        role="user",
        content=data.content,
        status="complete",
    )

    # Create pending assistant message
    assistant_msg = chats.create_assistant_message(user_id, chat_id)

    # Build messages for API
    webhook_secret = user.webhook_secret if user else None
    model = data.model or (user.model if user else None) or DEFAULT_MODEL
    system_prompt = build_system_prompt(model=model)
    chat_messages = chats.get_messages(chat_id)

    # Convert to API format (exclude the pending assistant message)
    messages = [{"role": "system", "content": system_prompt}]
    for m in chat_messages:
        if m["id"] != assistant_msg.id and m["status"] == "complete":
            messages.append({"role": m["role"], "content": m["content"]})

    # Initialize stream state BEFORE starting background task (prevents race condition)
    active_streams[assistant_msg.id] = {
        "content": "",
        "status": "pending",
        "subscribers": set(),
    }

    # Start inference as async task (not BackgroundTasks - needs to run concurrently)
    notify_url = get_notify_url(webhook_secret) if webhook_secret else None
    asyncio.create_task(
        run_inference(
            user_id=user_id,
            chat_id=chat_id,
            message_id=assistant_msg.id,
            api_key=auth.token,  # Pass JWT for backend auth
            model=model,
            messages=messages,
            notify_url=notify_url,
        )
    )

    return SendMessageResponse(
        user_message_id=user_msg.id,
        assistant_message_id=assistant_msg.id,
        status="processing",
    )


# =============================================================================
# SSE Streaming endpoint
# =============================================================================


@router.post("/{chat_id}/messages/stream")
async def send_message_stream(
    chat_id: str,
    data: MessageCreate,
    auth: AuthInfo = Depends(require_auth),
):
    """
    Send a message and stream the AI response via SSE.

    Returns a streaming response with Server-Sent Events:
    - data: <token> - Each token as it's generated
    - event: done - When streaming is complete
    """
    user_id = auth.user_id

    # Verify chat exists and belongs to user
    chat = chats.get_chat(chat_id)
    if not chat or chat.user_id != user_id:
        raise HTTPException(status_code=404, detail="Chat not found")

    # Get user for model preference
    user = users.get_user(user_id)

    # Store user message
    user_msg = chats.add_message(
        user_id=user_id,
        chat_id=chat_id,
        role="user",
        content=data.content,
        status="complete",
    )

    # Create pending assistant message
    assistant_msg = chats.create_assistant_message(user_id, chat_id)

    # Build messages for API
    webhook_secret = user.webhook_secret if user else None
    model = data.model or (user.model if user else None) or DEFAULT_MODEL
    system_prompt = build_system_prompt(model=model)
    chat_messages = chats.get_messages(chat_id)

    # Convert to API format (exclude the pending assistant message)
    messages = [{"role": "system", "content": system_prompt}]
    for m in chat_messages:
        if m["id"] != assistant_msg.id and m["status"] == "complete":
            messages.append({"role": m["role"], "content": m["content"]})

    notify_url = get_notify_url(webhook_secret) if webhook_secret else None

    async def generate_sse():
        """Generator that yields SSE formatted events."""
        full_content = ""
        try:
            async for event in stream_completion(
                api_key=auth.token,  # Pass JWT for backend auth
                model=model,
                messages=messages,
                notify_url=notify_url,
            ):
                if event.type == "token":
                    full_content = event.content
                    yield f"data: {event.content}\n\n"

                elif event.type == "done":
                    # Update the assistant message with final content
                    chats.update_message_content(assistant_msg.id, full_content)
                    chats.update_message_status(assistant_msg.id, "complete")
                    yield f"event: done\ndata: {assistant_msg.id}\n\n"

                elif event.type == "error":
                    chats.update_message_status(assistant_msg.id, "error", error=event.content)
                    yield f"event: error\ndata: {event.content}\n\n"

        except Exception as e:
            logger.exception(f"SSE streaming error: {e}")
            chats.update_message_status(assistant_msg.id, "error", error=str(e))
            yield f"event: error\ndata: {str(e)}\n\n"

    return StreamingResponse(
        generate_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# =============================================================================
# Selection response endpoint
# =============================================================================


class SelectionResponse(BaseModel):
    selected_id: str  # ID of the selected option
    message_id: int  # ID of the selection message being responded to


class SelectionResponseResult(BaseModel):
    message_id: int  # ID of the created selection_response message
    status: str  # "processing" if tool will be executed, "cancelled" if cancelled
    tool_result: Optional[str] = None  # Tool result if executed immediately


@router.post("/{chat_id}/selection", response_model=SelectionResponseResult)
async def respond_to_selection(
    chat_id: str,
    data: SelectionResponse,
    background_tasks: BackgroundTasks,
    auth: AuthInfo = Depends(require_auth),
):
    """
    Respond to a selection message.

    When the assistant presents options (type=selection), the frontend
    should call this endpoint with the user's choice.
    """
    user_id = auth.user_id

    # Verify chat exists and belongs to user
    chat = chats.get_chat(chat_id)
    if not chat or chat.user_id != user_id:
        raise HTTPException(status_code=404, detail="Chat not found")

    # Get the selection message
    selection_msg = chats.get_message(data.message_id)
    if not selection_msg or selection_msg.chat_id != chat_id:
        raise HTTPException(status_code=404, detail="Selection message not found")

    if selection_msg.type != "selection":
        raise HTTPException(status_code=400, detail="Message is not a selection")

    # Get the selected option
    meta = selection_msg.meta or {}
    options = meta.get("options", [])
    selected_option = next((o for o in options if o.get("id") == data.selected_id), None)

    if not selected_option:
        raise HTTPException(status_code=400, detail="Invalid selection")

    selected_label = selected_option.get("label", data.selected_id)
    tool_call = meta.get("tool_call")

    # Record the selection response
    response_msg = chats.add_selection_response(
        user_id=user_id,
        chat_id=chat_id,
        selected_id=data.selected_id,
        selected_label=selected_label,
        tool_call=tool_call,
    )

    # Handle cancellation
    if data.selected_id == "cancel":
        return SelectionResponseResult(
            message_id=response_msg.id,
            status="cancelled",
        )

    # If there's a tool call to execute, do it
    if tool_call and data.selected_id == "proceed":
        from core import execute_confirmed_tool

        user = users.get_user(user_id)
        webhook_secret = user.webhook_secret if user else None
        notify_url = get_notify_url(webhook_secret) if webhook_secret else None

        # Execute the tool in background
        async def run_tool_and_notify():
            tool_name = tool_call.get("name")
            tool_args = tool_call.get("arguments", {})

            async for event in execute_confirmed_tool(
                api_key=auth.token,  # Pass JWT for backend auth
                tool_name=tool_name,
                tool_args=tool_args,
                user_id=user_id,
                chat_id=chat_id,
                notify_url=notify_url,
            ):
                if event.type == "tool_result":
                    # Store result as assistant message
                    chats.add_message(
                        user_id=user_id,
                        chat_id=chat_id,
                        role="assistant",
                        content=f"Tool executed: {event.tool_result}",
                        status="complete",
                    )
                elif event.type == "error":
                    chats.add_message(
                        user_id=user_id,
                        chat_id=chat_id,
                        role="assistant",
                        content=f"Error: {event.content}",
                        status="error",
                    )

        background_tasks.add_task(run_tool_and_notify)

        return SelectionResponseResult(
            message_id=response_msg.id,
            status="processing",
        )

    # Default case - just record the response
    return SelectionResponseResult(
        message_id=response_msg.id,
        status="recorded",
    )


# =============================================================================
# WebSocket endpoint
# =============================================================================


@router.websocket("/{chat_id}/stream")
async def stream_chat(
    websocket: WebSocket,
    chat_id: str,
):
    """
    WebSocket endpoint for streaming chat responses.

    Connect to receive live tokens for any active message in the chat.
    Supports reconnection - will send current content on connect.

    Messages:
    - {"type": "subscribe", "message_id": 123} - Subscribe to a message stream
    - {"type": "token", "content": "..."} - Token update (full content so far)
    - {"type": "done", "content": "..."} - Stream complete
    - {"type": "error", "error": "..."} - Error occurred
    """
    await websocket.accept()

    # JWT auth via query param for WebSocket
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

    chat = chats.get_chat(chat_id)
    if not chat or chat.user_id != user_id:
        await websocket.close(code=4004, reason="Chat not found")
        return

    # Queue for this connection
    queue: asyncio.Queue = asyncio.Queue()
    subscribed_message_id: Optional[int] = None

    async def handle_client_messages():
        """Handle incoming WebSocket messages from client."""
        nonlocal subscribed_message_id
        try:
            while True:
                data = await websocket.receive_json()
                if data.get("type") == "subscribe":
                    message_id = data.get("message_id")
                    logger.info(f"[WS] Subscribe request for message_id={message_id}, in_active_streams={message_id in active_streams}")
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
        if subscribed_message_id and subscribed_message_id in active_streams:
            active_streams[subscribed_message_id]["subscribers"].discard(queue)
