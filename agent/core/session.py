"""
Chat session abstraction for frontends.

Provides a base class that handles the common inference loop,
with hooks for frontend-specific actions (sending messages, showing progress, etc.)
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from config import DEFAULT_MODEL
from .inference import stream_completion, StreamEvent
from .prompts import build_system_prompt

logger = logging.getLogger(__name__)


@dataclass
class SessionContext:
    """Context for a chat session."""
    user_id: str
    chat_id: str
    api_key: str
    webhook_secret: str
    model: str | None = None

    @property
    def effective_model(self) -> str:
        return self.model or DEFAULT_MODEL


class BaseChatSession(ABC):
    """
    Base class for chat sessions across different frontends.

    Subclasses implement the abstract methods to handle frontend-specific
    output (Telegram messages, WebSocket broadcasts, CLI output, etc.)
    """

    def __init__(self, context: SessionContext):
        self.context = context
        self.final_response = ""

    def build_messages(
        self,
        chat_messages: list[dict],
        extra_instructions: str | None = None,
    ) -> list[dict]:
        """
        Build the messages array for the API call.

        Args:
            chat_messages: List of message dicts from the database
            extra_instructions: Optional frontend-specific instructions

        Returns:
            List of messages in OpenAI format
        """
        system_prompt = build_system_prompt(
            self.context.webhook_secret,
            extra_instructions,
        )

        messages = [{"role": "system", "content": system_prompt}]

        for m in chat_messages:
            if m.get("status") == "complete":
                messages.append({"role": m["role"], "content": m["content"]})

        return messages

    async def run(
        self,
        messages: list[dict],
    ) -> str:
        """
        Run the inference loop, calling hooks for each event.

        Args:
            messages: Messages array in OpenAI format

        Returns:
            Final response content
        """
        self.final_response = ""

        try:
            async for event in stream_completion(
                api_key=self.context.api_key,
                model=self.context.effective_model,
                messages=messages,
                user_id=self.context.user_id,
                chat_id=self.context.chat_id,
            ):
                await self._handle_event(event)

        except Exception as e:
            logger.error(f"Session error: {e}")
            await self.on_error(str(e))
            raise

        return self.final_response

    async def _handle_event(self, event: StreamEvent) -> None:
        """Dispatch event to the appropriate handler."""
        if event.type == "token":
            self.final_response = event.content
            await self.on_token(event.content)

        elif event.type == "tool_start":
            await self.on_tool_start(event.tool_name)

        elif event.type == "tool_result":
            await self.on_tool_result(
                event.tool_name,
                event.tool_args,
                event.tool_result,
            )

        elif event.type == "done":
            self.final_response = event.content
            await self.on_done(event.content)

        elif event.type == "error":
            await self.on_error(event.content)

    # =========================================================================
    # Abstract methods - implement these in frontend subclasses
    # =========================================================================

    @abstractmethod
    async def on_token(self, content: str) -> None:
        """
        Called for each token update.

        Args:
            content: Full accumulated response text so far
        """
        pass

    @abstractmethod
    async def on_tool_start(self, tool_names: str) -> None:
        """
        Called when tool execution starts.

        Args:
            tool_names: Comma-separated names of tools being called
        """
        pass

    @abstractmethod
    async def on_tool_result(
        self,
        tool_name: str,
        tool_args: dict,
        tool_result: str,
    ) -> None:
        """
        Called when a tool returns a result.

        Args:
            tool_name: Name of the tool that completed
            tool_args: Arguments that were passed to the tool
            tool_result: Result returned by the tool
        """
        pass

    @abstractmethod
    async def on_done(self, content: str) -> None:
        """
        Called when inference is complete.

        Args:
            content: Final complete response
        """
        pass

    @abstractmethod
    async def on_error(self, error: str) -> None:
        """
        Called when an error occurs.

        Args:
            error: Error message
        """
        pass
