"""
Chat handler - main message processing with AI inference.
"""

import time
import re
from telegram import Update
from telegram.ext import ContextTypes

from config import WEBHOOK_PREFIX
from db import (
    get_user,
    get_or_create_user,
    add_message,
    get_context_messages,
    update_message_by_telegram_id,
    new_context,
    DEFAULT_MODEL,
)
from services.inference import chat_completion_stream
from keyboards import after_response_keyboard, new_context_keyboard_with_id
from handlers.onboarding import handle_api_key_input, show_welcome

# Minimum time between message edits (Telegram rate limit protection)
MIN_EDIT_INTERVAL = 1.0


def build_system_prompt(user) -> str:
    """Build system prompt with user-specific notify_url for renders."""
    notify_url = f"{WEBHOOK_PREFIX}/render/{user.webhook_secret}"
    return f"""You are a helpful AI assistant in a Telegram chat.

CRITICAL TOOL USAGE RULES:
1. Use each tool ONCE - do NOT call the same tool multiple times
2. After using tools, provide a SUMMARY of what you did
3. NEVER make redundant or duplicate tool calls
4. If you've completed an action, summarize the results and STOP

When creating renders (images/videos), ALWAYS include this notify_url parameter:
notify_url: {notify_url}

This ensures the rendered result will be sent back to this chat automatically."""


def extract_text_from_message(text: str) -> str:
    """Extract plain text from message, stripping HTML tags if present."""
    # Remove HTML tags
    clean = re.sub(r'<[^>]+>', '', text or "")
    return clean.strip()


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming text messages."""
    # Handle edited messages
    if update.edited_message:
        await handle_edited_message(update, context)
        return

    if not update.message:
        return

    chat_id = update.effective_chat.id

    # Check if this is API key input
    if await handle_api_key_input(update, context):
        return

    # Check if user is in API key change flow
    if context.user_data.get("changing_api_key"):
        from handlers.settings import handle_new_api_key
        await handle_new_api_key(update, context)
        return

    # Get user from DB
    user = get_user(chat_id)

    # No API key? Show welcome/onboarding
    if not user or not user.api_key:
        await show_welcome(update, context)
        return

    # Extract message text
    raw_message = update.message.text or ""
    message_text = extract_text_from_message(raw_message)

    if not message_text:
        return

    model = user.model or DEFAULT_MODEL
    telegram_message_id = update.message.message_id

    # Store user message in DB
    add_message(
        chat_id=chat_id,
        context_id=user.current_context_id,
        role="user",
        content=message_text,
        message_id=telegram_message_id,
    )

    # Build messages for API call: system prompt + context history
    system_prompt = build_system_prompt(user)
    context_messages = get_context_messages(chat_id, user.current_context_id)

    messages = [{"role": "system", "content": system_prompt}] + context_messages

    # Send typing indicator
    await update.message.chat.send_action("typing")

    # Track last edit time and content for rate limiting
    last_edit_time = 0.0
    last_sent_text = ""
    response_msg = None
    stream_start_time = time.time()

    async def on_stream_update(text: str):
        """Called when we have new text to display."""
        nonlocal last_edit_time, last_sent_text, response_msg, stream_start_time

        # Skip if text is only whitespace
        if not text or text.strip() == "":
            return

        now = time.time()

        # If no message sent yet, wait 1 second to accumulate content
        if response_msg is None:
            time_since_start = now - stream_start_time
            if time_since_start < 1.0:
                return  # Wait for 1 second of accumulation

            # Send first message with accumulated content (or placeholder if no content yet)
            if text.strip():
                response_msg = await update.message.reply_text(text + " ▌")
            else:
                response_msg = await update.message.reply_text("... ⏳")
            last_edit_time = now
            last_sent_text = text
            return

        time_since_last = now - last_edit_time

        # Check if text ends with punctuation
        ends_with_punctuation = text.rstrip()[-1:] in ".!?,;:\n"

        # Only update if:
        # 1. At least 1 second has passed since last update
        # 2. Text ends with punctuation (sentence boundary)
        should_update = time_since_last >= MIN_EDIT_INTERVAL and ends_with_punctuation

        if not should_update:
            return  # Skip this update

        try:
            await response_msg.edit_text(text + " ▌")
            last_edit_time = now
            last_sent_text = text
        except Exception as e:
            # Log edit errors for debugging (but continue)
            import logging
            logging.getLogger(__name__).warning(f"Message edit failed: {e}")

    # Stream the response with full conversation history
    final_response = await chat_completion_stream(
        user.api_key, model, messages, on_stream_update
    )

    # If response was very fast and we never sent a message, send it now and we're done
    if response_msg is None:
        response_msg = await update.message.reply_text(final_response, reply_markup=after_response_keyboard())
        # Store assistant response in DB
        add_message(
            chat_id=chat_id,
            context_id=user.current_context_id,
            role="assistant",
            content=final_response,
            message_id=response_msg.message_id,
        )
        return

    # Store assistant response in DB
    add_message(
        chat_id=chat_id,
        context_id=user.current_context_id,
        role="assistant",
        content=final_response,
        message_id=response_msg.message_id,
    )

    # Final edit with keyboard (remove cursor)
    # Try Markdown first, fall back to plain text if parsing fails
    try:
        await response_msg.edit_text(
            final_response,
            reply_markup=after_response_keyboard(),
            parse_mode="Markdown",
        )
    except Exception:
        # Markdown parsing failed, try plain text
        try:
            await response_msg.edit_text(
                final_response,
                reply_markup=after_response_keyboard(),
            )
        except Exception:
            # If edit fails, send new message
            await update.message.reply_text(
                final_response,
                reply_markup=after_response_keyboard(),
            )


async def handle_edited_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle edited messages - update in DB."""
    edited = update.edited_message
    if not edited or not edited.text:
        return

    chat_id = edited.chat.id
    message_id = edited.message_id
    new_content = extract_text_from_message(edited.text)

    # Update message in DB if it exists
    updated = update_message_by_telegram_id(chat_id, message_id, new_content)
    if updated:
        # Optionally acknowledge the edit (or stay silent)
        pass


async def cmd_newcontext(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /newcontext command - create new context."""
    chat_id = update.effective_chat.id

    # Get or create user
    user = get_or_create_user(chat_id)

    # Create new context
    new_context_id = new_context(chat_id)

    # Send marker message with resume button
    from handlers.settings import NEW_CONTEXT_MESSAGE, NEW_CONTEXT_MARKER
    marker_msg = await update.message.reply_text(
        NEW_CONTEXT_MESSAGE,
        parse_mode="HTML",
        reply_markup=new_context_keyboard_with_id(new_context_id),
    )

    # Store marker in DB
    add_message(
        chat_id=chat_id,
        context_id=new_context_id,
        role="context_marker",
        content=NEW_CONTEXT_MARKER,
        message_id=marker_msg.message_id,
    )
