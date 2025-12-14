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
from pydantic import BaseModel

from frontends.web.dependencies import require_api_key
from frontends.web.state import active_streams
from services import chats, users
from core import stream_completion
from core.prompts import build_system_prompt
from config import DEFAULT_MODEL

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
):
    """
    Run inference in background and update message status.
    Broadcasts tokens to WebSocket subscribers.

    Args:
        require_confirmation: If True, tools in TOOLS_REQUIRING_CONFIRMATION
            will create selection messages for user confirmation.
    """
    import json as json_module

    # Initialize stream state
    active_streams[message_id] = {
        "content": "",
        "status": "streaming",
        "subscribers": set(),
    }

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
        ):
            if event.type == "token":
                final_content = event.content
                active_streams[message_id]["content"] = final_content

                # Broadcast to subscribers
                for queue in active_streams[message_id]["subscribers"]:
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
    background_tasks: BackgroundTasks,
    user_id: str = Depends(require_api_key),
):
    """
    Send a message and start AI response generation.

    Returns immediately with message IDs. The assistant response will be
    generated in the background. Connect to the WebSocket endpoint to
    receive streaming tokens.
    """
    # Verify chat exists and belongs to user
    chat = chats.get_chat(chat_id)
    if not chat or chat.user_id != user_id:
        raise HTTPException(status_code=404, detail="Chat not found")

    # Get user for API key and model
    user = users.get_user(user_id)
    if not user or not user.api_key:
        raise HTTPException(status_code=400, detail="User has no API key configured")

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
    system_prompt = build_system_prompt(user.webhook_secret)
    chat_messages = chats.get_messages(chat_id)

    # Convert to API format (exclude the pending assistant message)
    messages = [{"role": "system", "content": system_prompt}]
    for m in chat_messages:
        if m["id"] != assistant_msg.id and m["status"] == "complete":
            messages.append({"role": m["role"], "content": m["content"]})

    # Start inference in background
    background_tasks.add_task(
        run_inference,
        user_id=user_id,
        chat_id=chat_id,
        message_id=assistant_msg.id,
        api_key=user.api_key,
        model=user.model or DEFAULT_MODEL,
        messages=messages,
    )

    return SendMessageResponse(
        user_message_id=user_msg.id,
        assistant_message_id=assistant_msg.id,
        status="processing",
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
    user_id: str = Depends(require_api_key),
):
    """
    Respond to a selection message.

    When the assistant presents options (type=selection), the frontend
    should call this endpoint with the user's choice.
    """
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
        from services import users

        user = users.get_user(user_id)
        if not user or not user.api_key:
            raise HTTPException(status_code=400, detail="User has no API key configured")

        # Execute the tool in background
        async def run_tool_and_notify():
            tool_name = tool_call.get("name")
            tool_args = tool_call.get("arguments", {})

            async for event in execute_confirmed_tool(
                api_key=user.api_key,
                tool_name=tool_name,
                tool_args=tool_args,
                user_id=user_id,
                chat_id=chat_id,
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

    # Simple auth via query param for WebSocket
    # In production, use a proper token
    api_key = websocket.query_params.get("api_key")
    if not api_key:
        await websocket.close(code=4001, reason="Missing api_key")
        return

    # Verify user owns this chat
    from db.models import get_session, User
    with get_session() as session:
        user = session.query(User).filter(User.api_key == api_key).first()
        if not user:
            await websocket.close(code=4001, reason="Invalid api_key")
            return
        user_id = user.user_id

    chat = chats.get_chat(chat_id)
    if not chat or chat.user_id != user_id:
        await websocket.close(code=4004, reason="Chat not found")
        return

    # Queue for this connection
    queue: asyncio.Queue = asyncio.Queue()
    subscribed_message_id: Optional[int] = None

    try:
        while True:
            # Wait for client message or queue item
            try:
                data = await asyncio.wait_for(websocket.receive_json(), timeout=0.1)

                if data.get("type") == "subscribe":
                    message_id = data.get("message_id")
                    if message_id and message_id in active_streams:
                        # Unsubscribe from previous
                        if subscribed_message_id and subscribed_message_id in active_streams:
                            active_streams[subscribed_message_id]["subscribers"].discard(queue)

                        # Subscribe to new
                        subscribed_message_id = message_id
                        active_streams[message_id]["subscribers"].add(queue)

                        # Send current state
                        state = active_streams[message_id]
                        await websocket.send_json({
                            "type": "state",
                            "content": state["content"],
                            "status": state["status"],
                        })

            except asyncio.TimeoutError:
                pass

            # Check queue for updates
            try:
                while True:
                    event = queue.get_nowait()
                    await websocket.send_json(event)
            except asyncio.QueueEmpty:
                pass

    except WebSocketDisconnect:
        pass
    finally:
        # Cleanup
        if subscribed_message_id and subscribed_message_id in active_streams:
            active_streams[subscribed_message_id]["subscribers"].discard(queue)
