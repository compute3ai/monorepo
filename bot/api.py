"""
REST API endpoints for web clients.

Provides thread and message management APIs authenticated via JWT tokens
from the backend auth service. JWTs are validated by passing them through
to the backend /user endpoint.
"""

import logging
from typing import Optional
from datetime import datetime

import httpx
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import db
from core import ChatEngine
from config import API_BASE_URL
from renders import (
    add_render_notification,
    get_unread_render_notifications,
    mark_render_notifications_read,
)

logger = logging.getLogger(__name__)


# FastAPI app
app = FastAPI(
    title="Bot API",
    description="REST API for chat threads and messages",
    version="1.0.0",
)


# =============================================================================
# Auth dependency
# =============================================================================

async def get_current_user(authorization: str = Header(...)) -> tuple[str, str]:
    """
    Validate JWT by calling backend /user endpoint.

    Expects: Authorization: Bearer <jwt>
    Returns: tuple of (user_id, jwt_token) - jwt can be used as api_key for /v1 calls
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization[7:]  # Strip "Bearer "

    # Validate by calling backend /user
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{API_BASE_URL}/user",
                headers={"Authorization": authorization},
            )
            if response.status_code == 401:
                raise HTTPException(status_code=401, detail="Invalid or expired token")
            if response.status_code != 200:
                raise HTTPException(status_code=401, detail="Authentication failed")

            user_info = response.json()
            user_id = user_info.get("id") or user_info.get("user_id")
            if not user_id:
                raise HTTPException(status_code=401, detail="Invalid token: missing user_id")

            return (str(user_id), token)
        except httpx.RequestError as e:
            logger.error(f"Backend auth request failed: {e}")
            raise HTTPException(status_code=503, detail="Authentication service unavailable")


# =============================================================================
# Pydantic models
# =============================================================================

class ThreadResponse(BaseModel):
    id: str
    title: Optional[str]
    created_at: datetime
    updated_at: datetime


class ThreadListResponse(BaseModel):
    threads: list[ThreadResponse]


class CreateThreadRequest(BaseModel):
    title: Optional[str] = None


class MessageResponse(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime


class ThreadMessagesResponse(BaseModel):
    messages: list[MessageResponse]


class SendMessageRequest(BaseModel):
    content: str


class UpdateMessageRequest(BaseModel):
    content: str


class MessageSentResponse(BaseModel):
    user_message_id: int
    assistant_message_id: int
    assistant_content: str


class WebhookSecretResponse(BaseModel):
    webhook_secret: str
    webhook_url: str


class RenderNotificationResponse(BaseModel):
    id: int
    render_id: str
    status: str
    result_url: Optional[str]
    error: Optional[str]
    created_at: datetime


class RenderNotificationListResponse(BaseModel):
    notifications: list[RenderNotificationResponse]


class MarkReadRequest(BaseModel):
    notification_ids: Optional[list[int]] = None  # None = mark all read


class RenderWebhookPayload(BaseModel):
    id: str
    status: str
    result_url: Optional[str] = None
    error: Optional[str] = None


# =============================================================================
# Thread endpoints
# =============================================================================

@app.get("/threads", response_model=ThreadListResponse)
async def list_threads(
    limit: int = 20,
    auth: tuple[str, str] = Depends(get_current_user)
):
    """List user's threads, ordered by most recent activity."""
    user_id, token = auth

    # Ensure user exists and has the JWT as their api_key
    user = db.get_or_create_user_by_user_id(user_id)
    if not user.api_key:
        db.set_user_api_key(user_id, token)

    threads = db.get_user_threads_by_user_id(user_id, limit)
    return ThreadListResponse(
        threads=[
            ThreadResponse(
                id=t.id,
                title=t.title,
                created_at=t.created_at,
                updated_at=t.updated_at,
            )
            for t in threads
        ]
    )


@app.post("/threads", response_model=ThreadResponse)
async def create_thread(
    request: CreateThreadRequest,
    auth: tuple[str, str] = Depends(get_current_user)
):
    """Create a new thread."""
    user_id, token = auth

    # Ensure user exists
    user = db.get_or_create_user_by_user_id(user_id)
    if not user.api_key:
        db.set_user_api_key(user_id, token)

    thread = db.create_thread_for_user(user_id, request.title)
    return ThreadResponse(
        id=thread.id,
        title=thread.title,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
    )


@app.get("/threads/{thread_id}", response_model=ThreadResponse)
async def get_thread(
    thread_id: str,
    auth: tuple[str, str] = Depends(get_current_user)
):
    """Get a specific thread."""
    user_id, _ = auth

    thread = db.get_thread(thread_id)
    if not thread or thread.user_id != user_id:
        raise HTTPException(status_code=404, detail="Thread not found")

    return ThreadResponse(
        id=thread.id,
        title=thread.title,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
    )


@app.delete("/threads/{thread_id}")
async def delete_thread(
    thread_id: str,
    auth: tuple[str, str] = Depends(get_current_user)
):
    """Delete a thread."""
    user_id, _ = auth

    success = db.delete_thread_by_user_id(thread_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Thread not found")
    return {"status": "deleted"}


# =============================================================================
# Message endpoints
# =============================================================================

@app.get("/threads/{thread_id}/messages", response_model=ThreadMessagesResponse)
async def list_messages(
    thread_id: str,
    auth: tuple[str, str] = Depends(get_current_user)
):
    """Get all messages in a thread."""
    user_id, _ = auth

    thread = db.get_thread(thread_id)
    if not thread or thread.user_id != user_id:
        raise HTTPException(status_code=404, detail="Thread not found")

    # Get full message objects (not just role/content dicts)
    with db.get_session() as session:
        messages = session.query(db.Message).filter(
            db.Message.thread_id == thread_id
        ).order_by(db.Message.created_at.asc()).all()

        return ThreadMessagesResponse(
            messages=[
                MessageResponse(
                    id=m.id,
                    role=m.role,
                    content=m.content,
                    created_at=m.created_at,
                )
                for m in messages
            ]
        )


@app.post("/threads/{thread_id}/messages", response_model=MessageSentResponse)
async def send_message(
    thread_id: str,
    request: SendMessageRequest,
    auth: tuple[str, str] = Depends(get_current_user)
):
    """
    Send a message and get AI response.

    This is a non-streaming endpoint that waits for the full response.
    For streaming, use POST /threads/{thread_id}/messages/stream
    """
    user_id, token = auth

    thread = db.get_thread(thread_id)
    if not thread or thread.user_id != user_id:
        raise HTTPException(status_code=404, detail="Thread not found")

    # Ensure user has api_key set (use JWT)
    user = db.get_user_by_user_id(user_id)
    if not user or not user.api_key:
        db.set_user_api_key(user_id, token)

    engine = ChatEngine(db)

    try:
        result = await engine.send_message(
            user_id=user_id,
            thread_id=thread_id,
            content=request.content,
        )
        return MessageSentResponse(
            user_message_id=0,  # We don't track this in current impl
            assistant_message_id=result.message_id,
            assistant_content=result.content,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/threads/{thread_id}/messages/stream")
async def send_message_stream(
    thread_id: str,
    request: SendMessageRequest,
    auth: tuple[str, str] = Depends(get_current_user)
):
    """
    Send a message and stream the AI response via SSE.

    Returns Server-Sent Events with the response chunks.
    """
    user_id, token = auth

    thread = db.get_thread(thread_id)
    if not thread or thread.user_id != user_id:
        raise HTTPException(status_code=404, detail="Thread not found")

    # Ensure user has api_key set (use JWT)
    user = db.get_user_by_user_id(user_id)
    if not user or not user.api_key:
        db.set_user_api_key(user_id, token)

    engine = ChatEngine(db)

    async def generate():
        chunks_sent = set()

        async def on_chunk(text: str):
            # Only send new content
            if text not in chunks_sent:
                chunks_sent.add(text)
                yield f"data: {text}\n\n"

        try:
            result = await engine.send_message(
                user_id=user_id,
                thread_id=thread_id,
                content=request.content,
                on_chunk=on_chunk,
            )
            # Send final message with metadata
            yield f"event: done\ndata: {result.message_id}\n\n"
        except ValueError as e:
            yield f"event: error\ndata: {str(e)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@app.post("/threads/{thread_id}/messages/{message_id}/update", response_model=MessageSentResponse)
async def update_message(
    thread_id: str,
    message_id: int,
    request: UpdateMessageRequest,
    auth: tuple[str, str] = Depends(get_current_user)
):
    """
    Update a message and regenerate from that point.

    This truncates the thread at the specified message, updates its content,
    and generates a new AI response.
    """
    user_id, token = auth

    thread = db.get_thread(thread_id)
    if not thread or thread.user_id != user_id:
        raise HTTPException(status_code=404, detail="Thread not found")

    # Ensure user has api_key set (use JWT)
    user = db.get_user_by_user_id(user_id)
    if not user or not user.api_key:
        db.set_user_api_key(user_id, token)

    engine = ChatEngine(db)

    try:
        result = await engine.update_message(
            user_id=user_id,
            thread_id=thread_id,
            message_id=message_id,
            new_content=request.content,
        )
        return MessageSentResponse(
            user_message_id=message_id,
            assistant_message_id=result.message_id,
            assistant_content=result.content,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Webhook & Notification endpoints
# =============================================================================

@app.get("/webhook-secret", response_model=WebhookSecretResponse)
async def get_webhook_secret(
    auth: tuple[str, str] = Depends(get_current_user)
):
    """
    Get user's webhook secret for render notifications.

    Use this URL when creating renders to receive completion notifications.
    """
    user_id, token = auth

    # Ensure user exists
    user = db.get_or_create_user_by_user_id(user_id)
    if not user.api_key:
        db.set_user_api_key(user_id, token)

    webhook_secret = db.get_user_webhook_secret(user_id)
    if not webhook_secret:
        raise HTTPException(status_code=500, detail="Failed to get webhook secret")

    # Build webhook URL - this goes to the API endpoint
    from config import API_BASE_URL
    webhook_url = f"{API_BASE_URL}/bot/api/render/{webhook_secret}"

    return WebhookSecretResponse(
        webhook_secret=webhook_secret,
        webhook_url=webhook_url,
    )


@app.get("/notifications", response_model=RenderNotificationListResponse)
async def get_notifications(
    auth: tuple[str, str] = Depends(get_current_user)
):
    """Get unread render notifications."""
    user_id, _ = auth

    notifications = get_unread_render_notifications(user_id)
    return RenderNotificationListResponse(
        notifications=[
            RenderNotificationResponse(
                id=n.id,
                render_id=n.render_id,
                status=n.status,
                result_url=n.result_url,
                error=n.error,
                created_at=n.created_at,
            )
            for n in notifications
        ]
    )


@app.post("/notifications/read")
async def mark_notifications_read(
    request: MarkReadRequest,
    auth: tuple[str, str] = Depends(get_current_user)
):
    """Mark render notifications as read."""
    user_id, _ = auth

    count = mark_render_notifications_read(user_id, request.notification_ids)
    return {"marked_read": count}


@app.post("/render/{webhook_secret}")
async def render_webhook(
    webhook_secret: str,
    payload: RenderWebhookPayload,
):
    """
    Render completion webhook for web clients.

    This endpoint stores render results for web clients to poll.
    No authentication required - webhook_secret identifies the user.
    """
    # Look up user by webhook secret
    user = db.get_user_by_webhook_secret(webhook_secret)
    if not user:
        logger.warning("Invalid webhook secret for render callback")
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    logger.info(f"Render webhook: user_id={user.user_id} render_id={payload.id} status={payload.status}")

    # Store notification for web client to poll
    add_render_notification(
        user_id=user.user_id,
        render_id=payload.id,
        status=payload.status,
        result_url=payload.result_url,
        error=payload.error,
    )

    return {"status": "ok"}


# =============================================================================
# Health check
# =============================================================================

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}
