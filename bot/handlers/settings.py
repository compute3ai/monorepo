"""
Menu handlers - settings, renders, model selection and API key management.
"""

from telegram import Update
from telegram.ext import ContextTypes

from db import (
    get_user,
    get_or_create_user,
    set_api_key,
    set_model,
    new_thread,
    set_free_account,
    DEFAULT_MODEL,
)
from renders import get_user_renders, get_render_by_render_id
from services.compute3 import verify_api_key, list_models, create_free_account
from services.mcp import call_mcp_tool
from keyboards import (
    menu_keyboard,
    settings_keyboard,
    model_picker_keyboard,
    after_response_keyboard,
    renders_list_keyboard,
    render_detail_keyboard,
    obfuscate_key,
)


async def handle_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all menu/settings-related callbacks."""
    query = update.callback_query
    await query.answer()

    chat_id = update.effective_chat.id
    data = query.data

    if data == "start_free":
        await handle_start_free(query, chat_id, context)

    elif data == "menu" or data == "settings":
        await show_menu(query, chat_id)

    elif data == "renders":
        await show_renders_list(query, chat_id)

    elif data.startswith("render:"):
        render_id = data.split(":", 1)[1]
        await show_render_detail(query, chat_id, render_id)

    elif data.startswith("render_refresh:"):
        render_id = data.split(":", 1)[1]
        await refresh_render_status(query, chat_id, render_id)

    elif data == "noop":
        pass  # Do nothing for placeholder buttons

    elif data == "change_model":
        await show_model_picker(query, chat_id)

    elif data.startswith("select_model:"):
        model = data.split(":", 1)[1]
        await select_model(query, chat_id, model)

    elif data == "change_api_key":
        await prompt_api_key_change(query, context)

    elif data == "new_context":
        # Create new thread
        chat_id = update.effective_chat.id
        user = get_or_create_user(chat_id)
        thread = new_thread(chat_id)

        await query.message.reply_text(
            "✨ <b>New conversation started!</b>\n\n"
            "<i>Previous messages won't be included in this context.</i>",
            parse_mode="HTML",
            reply_markup=after_response_keyboard(),
        )

    elif data == "back" or data == "cancel":
        context.user_data["changing_api_key"] = False
        await query.message.reply_text(
            "Send me a message to chat.",
            reply_markup=after_response_keyboard(),
        )


async def show_menu(query, chat_id: int):
    """Show the main menu."""
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
        f"☰ <b>Menu</b>\n\n"
        f"🤖 <b>Model:</b> {model}\n"
        f"🔑 <b>API Key:</b> <code>{api_key_display}</code>",
        parse_mode="HTML",
        reply_markup=menu_keyboard(),
    )


# Backwards compatibility
show_settings = show_menu


async def show_renders_list(query, chat_id: int):
    """Show list of user's renders."""
    user = get_user(chat_id)

    if not user:
        await query.message.reply_text("Please use /start first.")
        return

    # Get renders for this user
    renders = get_user_renders(user.user_id, limit=10)

    await query.message.reply_text(
        "🖼️ <b>Your Renders</b>\n\n"
        "<i>Tap a render to see details or refresh its status.</i>",
        parse_mode="HTML",
        reply_markup=renders_list_keyboard(renders),
    )


async def show_render_detail(query, chat_id: int, render_id: str):
    """Show details of a specific render."""
    user = get_user(chat_id)

    if not user:
        await query.message.reply_text("Please use /start first.")
        return

    # Get render from local DB
    render = get_render_by_render_id(render_id)

    if not render or render.user_id != user.user_id:
        await query.message.reply_text(
            "❌ Render not found.",
            reply_markup=renders_list_keyboard([]),
        )
        return

    # Status emoji
    status_emoji = {
        "pending": "⏳",
        "success": "✅",
        "failed": "❌",
        "cancelled": "🚫",
    }.get(render.status, "❓")

    # Build detail message
    short_id = render.render_id[:8]
    msg = (
        f"🖼️ <b>Render Details</b>\n\n"
        f"<b>ID:</b> <code>{short_id}</code>\n"
        f"<b>Status:</b> {status_emoji} {render.status}\n"
        f"<b>Template:</b> {render.template or 'N/A'}\n"
    )

    if render.prompt:
        prompt_preview = render.prompt[:100] + "..." if len(render.prompt) > 100 else render.prompt
        msg += f"<b>Prompt:</b> {prompt_preview}\n"

    if render.result_url:
        msg += f"\n<b>Result:</b> {render.result_url}\n"

    if render.error:
        msg += f"\n<b>Error:</b> {render.error}\n"

    await query.message.reply_text(
        msg,
        parse_mode="HTML",
        reply_markup=render_detail_keyboard(render_id),
    )

    # If completed with result_url, send the image/video
    if render.status == "success" and render.result_url:
        try:
            is_video = any(ext in render.result_url.lower() for ext in ['.mp4', '.webm', '.mov'])
            if is_video:
                await query.message.reply_video(video=render.result_url)
            else:
                await query.message.reply_photo(photo=render.result_url)
        except Exception:
            pass  # Silently fail if we can't send media


async def refresh_render_status(query, chat_id: int, render_id: str):
    """Refresh render status from the API."""
    user = get_user(chat_id)

    if not user or not user.api_key:
        await query.message.reply_text("Please set your API key first.")
        return

    await query.message.reply_text("🔄 Checking render status...")

    try:
        # Call MCP to get render status
        result = await call_mcp_tool(user.api_key, "get_render", {"render_id": render_id})

        if isinstance(result, str):
            import json
            data = json.loads(result)
        else:
            data = result

        state = data.get("state", "unknown")
        result_url = data.get("result_url")
        error = data.get("error")

        # Update local DB
        from renders import update_render_status
        status_map = {"completed": "success", "failed": "failed", "pending": "pending", "running": "pending"}
        local_status = status_map.get(state, state)
        update_render_status(render_id, local_status, result_url, error)

        # Show updated detail
        await show_render_detail(query, chat_id, render_id)

    except Exception as e:
        await query.message.reply_text(
            f"❌ Failed to refresh status: {e}",
            reply_markup=render_detail_keyboard(render_id),
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
