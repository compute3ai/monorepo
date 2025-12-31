"""
Telegram output handler - rate-limited streaming.

Telegram has rate limits on message edits, so we buffer tokens
and only flush on punctuation boundaries.
"""

import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Minimum time between message edits (Telegram rate limit protection)
MIN_EDIT_INTERVAL = 1.0

# Characters that trigger a flush
FLUSH_CHARS = {'.', ',', ':', ';', '!', '?', '*', '\n'}


class TelegramOutput:
    """
    Handles Telegram-specific output with rate limiting.

    Buffers tokens and flushes on punctuation boundaries to avoid
    hitting Telegram's rate limits on message edits.
    """

    def __init__(self, send_message_func, edit_message_func):
        """
        Args:
            send_message_func: async func(text, **kwargs) -> Message
            edit_message_func: async func(message, text, **kwargs) -> None
        """
        self.send_message = send_message_func
        self.edit_message = edit_message_func
        self.response_msg = None
        self.last_edit_time = 0.0
        self.last_sent_text = ""
        self.stream_start_time = time.time()

    async def on_token(self, full_text: str) -> None:
        """
        Handle a new token from the stream.

        Args:
            full_text: The full accumulated response text so far
        """
        if not full_text or full_text.strip() == "":
            return

        now = time.time()

        # If no message sent yet, wait 1 second to accumulate
        if self.response_msg is None:
            time_since_start = now - self.stream_start_time
            if time_since_start < 1.0:
                return

            # Send first message
            if full_text.strip():
                self.response_msg = await self.send_message(full_text + " ▌")
            else:
                self.response_msg = await self.send_message("... ⏳")
            self.last_edit_time = now
            self.last_sent_text = full_text
            return

        time_since_last = now - self.last_edit_time

        # Only update on punctuation boundaries with rate limiting
        ends_with_punctuation = full_text.rstrip()[-1:] in FLUSH_CHARS
        should_update = time_since_last >= MIN_EDIT_INTERVAL and ends_with_punctuation

        if not should_update:
            return

        try:
            await self.edit_message(self.response_msg, full_text + " ▌")
            self.last_edit_time = now
            self.last_sent_text = full_text
        except Exception as e:
            logger.warning(f"Message edit failed: {e}")

    async def on_tool_start(self, tool_names: str) -> None:
        """Show tool calling status."""
        status_text = f"🔧 Calling tools: {tool_names}..."

        if self.response_msg is None:
            self.response_msg = await self.send_message(status_text)
        else:
            try:
                await self.edit_message(self.response_msg, status_text)
            except Exception:
                pass

        self.last_edit_time = time.time()

    async def finalize(self, final_text: str, reply_markup=None):
        """
        Finalize the output with the complete response.

        Returns the final Message object.
        """
        if self.response_msg is None:
            self.response_msg = await self.send_message(final_text, reply_markup=reply_markup)
            return self.response_msg

        # Try Markdown first, fall back to plain text
        try:
            await self.edit_message(
                self.response_msg,
                final_text,
                reply_markup=reply_markup,
                parse_mode="Markdown",
            )
        except Exception:
            try:
                await self.edit_message(
                    self.response_msg,
                    final_text,
                    reply_markup=reply_markup,
                )
            except Exception:
                # If edit fails, send new message
                self.response_msg = await self.send_message(final_text, reply_markup=reply_markup)

        return self.response_msg

    async def send_error(self, error_text: str, reply_markup=None):
        """Send an error message with optional recovery buttons."""
        if self.response_msg is None:
            self.response_msg = await self.send_message(f"❌ {error_text}", reply_markup=reply_markup)
        else:
            try:
                await self.edit_message(self.response_msg, f"❌ {error_text}", reply_markup=reply_markup)
            except Exception:
                # If edit fails, send a new message
                self.response_msg = await self.send_message(f"❌ {error_text}", reply_markup=reply_markup)

        return self.response_msg
