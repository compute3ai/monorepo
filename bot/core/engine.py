"""
ChatEngine - transport-agnostic message processing.

This class handles all chat logic independent of the transport layer (Telegram, REST API, etc).
"""

import logging
from typing import Callable, Awaitable, Optional
from dataclasses import dataclass

from config import WEBHOOK_PREFIX
from services.inference import chat_completion_stream

logger = logging.getLogger(__name__)


@dataclass
class ChatResult:
    """Result of a chat operation."""
    content: str
    message_id: int  # DB message ID (not Telegram ID)
    thread_id: str


class ChatEngine:
    """
    Transport-agnostic chat engine.

    Handles message processing, thread management, and inference calls.
    Can be used by both Telegram handlers and REST API endpoints.
    """

    def __init__(self, db_module):
        """
        Initialize ChatEngine with database module.

        Args:
            db_module: The db module containing all database functions
        """
        self.db = db_module

    def _build_system_prompt(self, webhook_secret: str) -> str:
        """Build system prompt with user-specific notify_url for renders."""
        notify_url = f"{WEBHOOK_PREFIX}/render/{webhook_secret}"
        return f"""You are a helpful AI assistant with access to GPU compute tools.

CRITICAL TOOL USAGE RULES:
1. Use each tool ONCE - do NOT call the same tool multiple times
2. After using tools, provide a brief SUMMARY of what you did
3. NEVER make redundant or duplicate tool calls

RENDER TOOL USAGE (create_render):
When creating images or videos, use these EXACT parameters:
- type: "comfyui" (always use this)
- params: object containing:
  - template: MUST be one of these exact names:
    * Images: "flux_dev", "flux_schnell", "hidream_i1_full", "hidream_i1_fast"
    * Videos: "video_wan2_2_14B_t2v", "video_wan2_2_1_3B_t2v", "video_hunyuan"
  - prompt: your text description
  - gpu_type: "l40s" (default) or "rtxpro6000" for faster video
- notify_url: "{notify_url}"

Example for image:
{{"type": "comfyui", "params": {{"template": "flux_dev", "prompt": "a cat in space"}}, "notify_url": "{notify_url}"}}

Example for video:
{{"type": "comfyui", "params": {{"template": "video_wan2_2_14B_t2v", "prompt": "a cat floating in space", "gpu_type": "rtxpro6000"}}, "notify_url": "{notify_url}"}}

The render result will be sent back to this chat automatically when complete."""

    async def send_message(
        self,
        user_id: str,
        thread_id: str,
        content: str,
        on_chunk: Optional[Callable[[str], Awaitable[None]]] = None,
        telegram_message_id: Optional[int] = None,
    ) -> ChatResult:
        """
        Send a message and get AI response.

        Args:
            user_id: User identifier (UUID from backend or tg_{chat_id})
            thread_id: Thread ID to send message in
            content: Message content
            on_chunk: Optional callback for streaming updates
            telegram_message_id: Optional Telegram message ID (for TG transport)

        Returns:
            ChatResult with the assistant's response
        """
        # Get user
        user = self.db.get_user_by_user_id(user_id)
        if not user:
            raise ValueError(f"User not found: {user_id}")

        if not user.api_key:
            raise ValueError("User has no API key configured")

        # Store user message
        user_msg = self.db.add_message(
            user_id=user_id,
            thread_id=thread_id,
            role="user",
            content=content,
            telegram_message_id=telegram_message_id,
        )

        # Build messages for API call
        system_prompt = self._build_system_prompt(user.webhook_secret)
        thread_messages = self.db.get_thread_messages(thread_id)
        messages = [{"role": "system", "content": system_prompt}] + thread_messages

        # Default no-op callback if none provided
        async def noop_callback(text: str):
            pass

        callback = on_chunk or noop_callback

        # Get model
        model = user.model or self.db.DEFAULT_MODEL

        # Stream response
        final_response = await chat_completion_stream(
            user.api_key,
            model,
            messages,
            callback,
            user_id=user_id,
            thread_id=thread_id,
        )

        # Store assistant response
        assistant_msg = self.db.add_message(
            user_id=user_id,
            thread_id=thread_id,
            role="assistant",
            content=final_response,
        )

        return ChatResult(
            content=final_response,
            message_id=assistant_msg.id,
            thread_id=thread_id,
        )

    async def update_message(
        self,
        user_id: str,
        thread_id: str,
        message_id: int,
        new_content: str,
        on_chunk: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> ChatResult:
        """
        Update a message and regenerate from that point.

        This truncates the thread at the specified message, updates its content,
        and generates a new response.

        Args:
            user_id: User identifier
            thread_id: Thread ID
            message_id: DB message ID to update
            new_content: New content for the message
            on_chunk: Optional callback for streaming updates

        Returns:
            ChatResult with the new assistant's response
        """
        # Verify user owns this thread
        user = self.db.get_user_by_user_id(user_id)
        if not user:
            raise ValueError(f"User not found: {user_id}")

        if not user.api_key:
            raise ValueError("User has no API key configured")

        # Truncate thread at this message and update content
        self.db.truncate_thread_at_message(thread_id, message_id, new_content)

        # Build messages for API call (now with truncated history)
        system_prompt = self._build_system_prompt(user.webhook_secret)
        thread_messages = self.db.get_thread_messages(thread_id)
        messages = [{"role": "system", "content": system_prompt}] + thread_messages

        # Default no-op callback
        async def noop_callback(text: str):
            pass

        callback = on_chunk or noop_callback

        # Get model
        model = user.model or self.db.DEFAULT_MODEL

        # Stream response
        final_response = await chat_completion_stream(
            user.api_key,
            model,
            messages,
            callback,
            user_id=user_id,
            thread_id=thread_id,
        )

        # Store assistant response
        assistant_msg = self.db.add_message(
            user_id=user_id,
            thread_id=thread_id,
            role="assistant",
            content=final_response,
        )

        return ChatResult(
            content=final_response,
            message_id=assistant_msg.id,
            thread_id=thread_id,
        )

    def create_thread(self, user_id: str, title: Optional[str] = None) -> str:
        """
        Create a new thread for a user.

        Args:
            user_id: User identifier
            title: Optional thread title

        Returns:
            Thread ID
        """
        thread = self.db.create_thread_for_user(user_id, title)
        return thread.id

    def get_threads(self, user_id: str, limit: int = 20) -> list:
        """
        Get threads for a user.

        Args:
            user_id: User identifier
            limit: Max threads to return

        Returns:
            List of Thread objects
        """
        return self.db.get_user_threads_by_user_id(user_id, limit)

    def get_thread_messages(self, thread_id: str) -> list[dict]:
        """
        Get messages for a thread.

        Args:
            thread_id: Thread ID

        Returns:
            List of message dicts with role and content
        """
        return self.db.get_thread_messages(thread_id)
