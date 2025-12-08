"""
Settings handlers - model selection and API key management.
"""

from telegram import Update
from telegram.ext import ContextTypes

from db import get_user, get_or_create_user, set_api_key, set_model, set_context, new_context, add_message, get_message_by_telegram_id, resume_context, get_marker_telegram_id, set_free_account, DEFAULT_MODEL
from services.compute3 import verify_api_key, list_models, create_free_account
from keyboards import (
    settings_keyboard,
    model_picker_keyboard,
    after_response_keyboard,
    new_context_keyboard_with_id,
    obfuscate_key,
)

# Marker for new context - used to find context boundaries in chat history
# IMPORTANT: When scanning history, check BOTH:
#   1. message.text.startswith(NEW_CONTEXT_MARKER)
#   2. message.from_user.is_bot == True (sent by the bot, not user)
NEW_CONTEXT_MARKER = "#NewContext"
NEW_CONTEXT_MESSAGE = """#NewContext

<i>Messages before this point will be ignored.
Delete this message to restore full context, or tap "Resume" later to come back here.</i>"""


async def handle_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all settings-related callbacks."""
    query = update.callback_query
    await query.answer()

    chat_id = update.effective_chat.id
    data = query.data

    if data == "start_free":
        await handle_start_free(query, chat_id, context)

    elif data == "settings":
        await show_settings(query, chat_id)

    elif data == "change_model":
        await show_model_picker(query, chat_id)

    elif data.startswith("select_model:"):
        model = data.split(":", 1)[1]
        await select_model(query, chat_id, model)

    elif data == "change_api_key":
        await prompt_api_key_change(query, context)

    elif data == "new_context":
        # Create new context and send marker message
        chat_id = update.effective_chat.id
        user = get_or_create_user(chat_id)
        new_context_id = new_context(chat_id)

        # Send marker message with context_id in callback data
        marker_msg = await query.message.reply_text(
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

    elif data.startswith("resume_context:"):
        # User tapped "Resume this context" - merge contexts and delete marker
        marker_context_id = data.split(":", 1)[1]
        chat_id = update.effective_chat.id

        # Get the marker's telegram message_id before we delete it
        marker_msg_id = get_marker_telegram_id(chat_id, marker_context_id)

        # Merge messages back to previous context
        previous_context_id = resume_context(chat_id, marker_context_id)

        if previous_context_id:
            # Update user's current context to the merged one
            set_context(chat_id, previous_context_id)

            # Delete the marker message from Telegram
            if marker_msg_id:
                try:
                    await query.message.delete()
                except Exception:
                    pass  # Message might already be deleted

            await query.answer("Context resumed!", show_alert=False)
        else:
            await query.answer("Could not find context to resume", show_alert=True)

    elif data == "back" or data == "cancel":
        context.user_data["changing_api_key"] = False
        await query.message.reply_text(
            "Send me a message to chat.",
            reply_markup=after_response_keyboard(),
        )


async def show_settings(query, chat_id: int):
    """Show the settings menu."""
    user = get_user(chat_id)

    if not user:
        await query.message.reply_text("Please use /start first.")
        return

    model = user.model or DEFAULT_MODEL

    # Detect if user has real API key or JWT
    if user.api_key and user.api_key.startswith("c3_api_"):
        api_key_display = obfuscate_key(user.api_key)
    else:
        # Either no key or it's a JWT (free account)
        api_key_display = "No API Key set"

    await query.message.reply_text(
        f"⚙️ <b>Settings</b>\n\n"
        f"🤖 <b>Model:</b> {model}\n"
        f"🔑 <b>API Key:</b> <code>{api_key_display}</code>",
        parse_mode="HTML",
        reply_markup=settings_keyboard(),
    )


async def show_model_picker(query, chat_id: int):
    """Show the model selection keyboard."""
    user = get_user(chat_id)

    if not user or not user.api_key:
        await query.message.reply_text("Please set your API key first.")
        return

    await query.message.reply_text("🔄 Fetching available models...")

    models = await list_models(user.api_key)

    if not models:
        await query.message.reply_text(
            "❌ Could not fetch models. Please check your API key.",
            reply_markup=settings_keyboard(),
        )
        return

    current_model = user.model or DEFAULT_MODEL

    await query.message.reply_text(
        "🤖 <b>Select a model:</b>",
        parse_mode="HTML",
        reply_markup=model_picker_keyboard(models, current_model),
    )


async def select_model(query, chat_id: int, model: str):
    """Handle model selection."""
    set_model(chat_id, model)

    await query.message.reply_text(
        f"✅ Model changed to <b>{model}</b>",
        parse_mode="HTML",
        reply_markup=after_response_keyboard(),
    )


async def prompt_api_key_change(query, context: ContextTypes.DEFAULT_TYPE):
    """Prompt user to enter new API key."""
    context.user_data["changing_api_key"] = True

    await query.message.reply_text(
        "🔑 Please send your new Compute3 API key:",
    )


async def handle_new_api_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle new API key input during settings change."""
    chat_id = update.effective_chat.id
    potential_key = update.message.text.strip()

    await update.message.reply_text("🔄 Verifying your API key...")

    user_info = await verify_api_key(potential_key)

    if user_info:
        set_api_key(chat_id, potential_key)
        context.user_data["changing_api_key"] = False

        await update.message.reply_text(
            "✅ <b>API key updated!</b>",
            parse_mode="HTML",
            reply_markup=after_response_keyboard(),
        )
    else:
        await update.message.reply_text(
            "❌ Invalid API key. Please try again or tap Cancel.",
        )


async def handle_start_free(query, chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Handle start_free callback - create free guest account."""
    user = get_user(chat_id)

    # Check if user already has an API key
    if user and user.api_key:
        await query.message.reply_text(
            "✅ You already have an API key set!\n\n"
            "Send me a message to start chatting.",
            reply_markup=after_response_keyboard(),
        )
        return

    # Check if user already used their free account
    if user and user.free == 1:
        await query.message.reply_text(
            "❌ You've already used your free trial.\n\n"
            "Please create an API key at https://console.compute3.ai to continue using the bot.",
            disable_web_page_preview=True,
        )
        return

    # Show loading message
    await query.message.reply_text("🔄 Creating your free account...")

    # Call /auth/free to get JWT token
    jwt_token = await create_free_account()

    if jwt_token:
        # Store JWT and mark as free account used
        set_free_account(chat_id, jwt_token)
        context.user_data["awaiting_api_key"] = False

        await query.message.reply_text(
            "✅ <b>Free account activated!</b>\n\n"
            "You can now chat with the bot for 30 days.\n\n"
            "After 30 days, create an API key at https://console.compute3.ai to continue.\n\n"
            "Send me a message to start chatting!",
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=after_response_keyboard(),
        )
    else:
        # Import here to avoid circular dependency
        from keyboards import welcome_keyboard

        await query.message.reply_text(
            "❌ Failed to create free account. Please try again or enter your API key manually.",
            reply_markup=welcome_keyboard(),
        )
