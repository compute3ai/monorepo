"""
Telegram handlers - command and message handlers using TelegramOutput for streaming.
"""

import logging
import re
import httpx
from telegram import Update
from telegram.ext import ContextTypes

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from config import DEFAULT_MODEL, API_BASE_URL, URL_PREFIX, TELEGRAM_BOT_TOKEN
from c3 import AsyncHTTPClient, AsyncFiles
from services import users, chats
from core import stream_completion
from core.prompts import build_system_prompt
from .output import TelegramOutput
from .keyboards import after_response_keyboard, welcome_keyboard, error_keyboard


async def handle_stream_with_confirmation(
    output: TelegramOutput,
    user,
    model: str,
    messages: list,
    chat,
    notify_url: str,
) -> str | None:
    """
    Handle streaming completion with tool confirmation.
    Returns final response, or None if waiting for confirmation.
    """
    final_response = ""
    pending_tools = []  # Collect ALL tool confirmations

    async for event in stream_completion(
        api_key=user.api_key,
        model=model,
        messages=messages,
        user_id=user.user_id,
        chat_id=chat.id,
        notify_url=notify_url,
        require_confirmation=True,
    ):
        if event.type == "token":
            await output.on_token(event.content)
            final_response = event.content
        elif event.type == "tool_start":
            await output.on_tool_start(event.tool_name)
        elif event.type == "tool_confirmation":
            # Collect this tool - don't show UI yet, wait for all tools
            pending_tools.append({
                "tool_call_id": event.tool_call_id,
                "tool_name": event.tool_name,
                "arguments": event.tool_args if isinstance(event.tool_args, dict) else {},
            })
        elif event.type == "done":
            final_response = event.content
        elif event.type == "error":
            await output.send_error(event.content, reply_markup=error_keyboard())
            return None

    # After stream ends, if we have pending tools, show confirmation UI
    if pending_tools:
        # Finalize any text response first
        text_so_far = final_response.strip() if final_response else ""
        if text_so_far:
            await output.finalize(text_so_far)

        # Store ALL pending tools
        chats.set_pending_tools(chat.id, pending_tools)

        # Build summary of tools to run (no markdown - buttons don't support it)
        tool_lines = []
        for i, tool in enumerate(pending_tools, 1):
            name = tool["tool_name"].replace("_", " ").replace("flow ", "").title()
            # Get prompt if available - show more of it as caption
            prompt = tool["arguments"].get("prompt", "")
            if prompt:
                # Show up to 80 chars of prompt
                if len(prompt) > 80:
                    prompt = prompt[:80] + "..."
                tool_lines.append(f"{i}. {name}\n   \"{prompt}\"")
            else:
                tool_lines.append(f"{i}. {name}")

        summary = "\n".join(tool_lines)
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"✅ Run {len(pending_tools)}", callback_data="tool:run"),
                InlineKeyboardButton("❌ Cancel", callback_data="tool:cancel"),
            ]
        ])
        await output.send_message(f"Run these tools?\n\n{summary}", reply_markup=keyboard)
        return None  # Wait for user to click button

    return final_response


def get_notify_url(webhook_secret: str) -> str:
    """Construct the render notification webhook URL for a user."""
    return f"{API_BASE_URL}{URL_PREFIX}/tg/render/{webhook_secret}"

logger = logging.getLogger(__name__)


def extract_text(text: str) -> str:
    """Extract plain text, stripping HTML tags."""
    return re.sub(r'<[^>]+>', '', text or "").strip()


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    telegram_id = update.effective_chat.id
    user = users.get_or_create_telegram_user(telegram_id)

    if user.api_key:
        await update.message.reply_text(
            "Welcome back! You're all set up. Just send me a message to chat.\n\n"
            "Use /new to start a fresh conversation."
        )
    else:
        await update.message.reply_text(
            "Welcome to Compute3 Agent!\n\n"
            "I'm an AI assistant with access to GPU compute tools for image and video generation.\n\n"
            "To get started, you can either:\n"
            "- Get a free account to try it out\n"
            "- Send your API key if you have one",
            reply_markup=welcome_keyboard(),
        )


async def cmd_newcontext(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /new or /newcontext command - start a new chat."""
    telegram_id = update.effective_chat.id
    user = users.get_user_by_telegram_id(telegram_id)

    if not user or not user.api_key:
        await update.message.reply_text("Please set up your API key first with /start")
        return

    chats.new_chat(user.user_id)
    await update.message.reply_text("Started a new conversation. What would you like to discuss?")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming text messages."""
    # Handle edited messages
    if update.edited_message:
        await handle_edited_message(update, context)
        return

    if not update.message:
        return

    telegram_id = update.effective_chat.id

    # Check if user is in API key input mode
    if context.user_data.get("awaiting_api_key"):
        await handle_api_key_input(update, context)
        return

    # Get user
    user = users.get_user_by_telegram_id(telegram_id)
    if not user or not user.api_key:
        await cmd_start(update, context)
        return

    # Extract message text
    message_text = extract_text(update.message.text or "")
    if not message_text:
        return

    telegram_message_id = update.message.message_id
    chat = chats.get_or_create_current_chat(user.user_id)

    # Store user message
    chats.add_message(
        user_id=user.user_id,
        chat_id=chat.id,
        role="user",
        content=message_text,
        telegram_message_id=telegram_message_id,
    )

    # Send typing indicator
    await update.message.chat.send_action("typing")

    # Stream response
    model = user.model or DEFAULT_MODEL

    # Build messages
    system_prompt = build_system_prompt(model=model)
    chat_messages = chats.get_messages(chat.id)
    messages = [{"role": "system", "content": system_prompt}]
    for m in chat_messages:
        if m["status"] == "complete":
            messages.append({"role": m["role"], "content": m["content"]})

    # Create output handler
    async def send_msg(text, **kwargs):
        return await update.message.reply_text(text, **kwargs)

    async def edit_msg(msg, text, **kwargs):
        await msg.edit_text(text, **kwargs)

    output = TelegramOutput(send_msg, edit_msg)
    notify_url = get_notify_url(user.webhook_secret)

    final_response = await handle_stream_with_confirmation(
        output=output,
        user=user,
        model=model,
        messages=messages,
        chat=chat,
        notify_url=notify_url,
    )

    # If None, we're waiting for tool confirmation
    if final_response is None:
        return

    # Finalize and store - ensure we never send an empty message
    if not final_response or not final_response.strip():
        final_response = "I processed your request but have no response to show."
    response_msg = await output.finalize(final_response, reply_markup=after_response_keyboard())

    chats.add_message(
        user_id=user.user_id,
        chat_id=chat.id,
        role="assistant",
        content=final_response,
        telegram_message_id=response_msg.message_id,
    )


async def handle_edited_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle edited messages - regenerate response."""
    if not update.edited_message:
        return

    telegram_id = update.effective_chat.id
    user = users.get_user_by_telegram_id(telegram_id)
    if not user or not user.api_key:
        return

    message_text = extract_text(update.edited_message.text or "")
    if not message_text:
        return

    telegram_message_id = update.edited_message.message_id

    # Find the message in DB
    msg = chats.get_message_by_telegram_id(telegram_id, telegram_message_id)
    if not msg:
        return

    # Truncate chat at this message and update content
    chats.truncate_at_message(msg.chat_id, msg.id, message_text)

    # Rebuild and regenerate
    chat = chats.get_chat(msg.chat_id)
    if not chat:
        return

    model = user.model or DEFAULT_MODEL
    system_prompt = build_system_prompt(model=model)
    chat_messages = chats.get_messages(chat.id)
    messages = [{"role": "system", "content": system_prompt}]
    for m in chat_messages:
        if m["status"] == "complete":
            messages.append({"role": m["role"], "content": m["content"]})

    await update.edited_message.chat.send_action("typing")

    async def send_msg(text, **kwargs):
        return await update.edited_message.reply_text(text, **kwargs)

    async def edit_msg(msg, text, **kwargs):
        await msg.edit_text(text, **kwargs)

    output = TelegramOutput(send_msg, edit_msg)
    model = user.model or DEFAULT_MODEL
    notify_url = get_notify_url(user.webhook_secret)

    final_response = await handle_stream_with_confirmation(
        output=output,
        user=user,
        model=model,
        messages=messages,
        chat=chat,
        notify_url=notify_url,
    )

    if final_response is None:
        return

    response_msg = await output.finalize(final_response, reply_markup=after_response_keyboard())

    chats.add_message(
        user_id=user.user_id,
        chat_id=chat.id,
        role="assistant",
        content=final_response,
        telegram_message_id=response_msg.message_id,
    )


async def handle_api_key_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle API key input."""
    telegram_id = update.effective_chat.id
    api_key = (update.message.text or "").strip()

    if not api_key or len(api_key) < 10:
        await update.message.reply_text("That doesn't look like a valid API key. Please try again.")
        return

    user = users.get_or_create_telegram_user(telegram_id)
    users.set_api_key(user.user_id, api_key)
    context.user_data["awaiting_api_key"] = False

    await update.message.reply_text(
        "API key saved! You're all set.\n\n"
        "Send me a message to start chatting, or use /new to start a fresh conversation."
    )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callback queries from inline keyboards."""
    query = update.callback_query
    await query.answer()

    telegram_id = update.effective_chat.id
    data = query.data

    # Tool confirmation handlers
    if data == "tool:run":
        user = users.get_user_by_telegram_id(telegram_id)
        if user and user.api_key:
            chat = chats.get_or_create_current_chat(user.user_id)
            pending_tools = chats.get_pending_tools(chat.id)
            if pending_tools:
                from core.mcp import call_mcp_tool
                await query.edit_message_text(f"⏳ Running {len(pending_tools)} tool(s)...")
                notify_url = get_notify_url(user.webhook_secret)

                # Execute ALL pending tools
                results = []
                for tool in pending_tools:
                    await call_mcp_tool(
                        user.api_key,
                        tool["tool_name"],
                        tool["arguments"],
                        notify_url=notify_url,
                    )
                    tool_name = tool["tool_name"].replace("_", " ").replace("flow ", "").title()
                    results.append(f"✅ {tool_name}")

                # Show clean summary (no raw JSON)
                summary = "\n".join(results)
                await query.edit_message_text(f"✅ Started {len(pending_tools)} render(s)!\n\n{summary}\n\nResults will be sent when ready.")
            else:
                await query.edit_message_text("No pending tool calls found.")
        return

    elif data == "tool:cancel":
        user = users.get_user_by_telegram_id(telegram_id)
        if user:
            chat = chats.get_or_create_current_chat(user.user_id)
            chats.clear_pending_tools(chat.id)
            await query.edit_message_text("Cancelled.")
        return

    elif data == "new_context":
        user = users.get_user_by_telegram_id(telegram_id)
        if user and user.api_key:
            chats.new_chat(user.user_id)
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text("Started a new conversation.")

    elif data == "start_free":
        # TODO: Implement free account signup
        context.user_data["awaiting_api_key"] = True
        await query.edit_message_text(
            "Please send your Compute3 API key.\n\n"
            "You can get one at https://compute3.ai"
        )

    elif data == "menu":
        from .keyboards import menu_keyboard
        await query.edit_message_text("What would you like to do?", reply_markup=menu_keyboard())

    elif data == "back":
        await query.edit_message_reply_markup(reply_markup=after_response_keyboard())

    elif data == "renders":
        from .keyboards import renders_list_keyboard
        user = users.get_user_by_telegram_id(telegram_id)
        if user and user.api_key:
            # Fetch renders from C3 API
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    response = await client.get(
                        f"{API_BASE_URL}/api/renders",
                        headers={"Authorization": f"Bearer {user.api_key}"},
                    )
                    response.raise_for_status()
                    renders_data = response.json()
                    render_list = renders_data.get("items", [])
            except Exception as e:
                logger.error(f"Failed to fetch renders: {e}")
                render_list = []

            if not render_list:
                await query.edit_message_text(
                    "No renders found.",
                    reply_markup=after_response_keyboard(),
                )
                return

            await query.edit_message_text(
                "Your recent renders:",
                reply_markup=renders_list_keyboard(render_list),
            )

    elif data == "change_model":
        from .keyboards import model_picker_keyboard
        user = users.get_user_by_telegram_id(telegram_id)
        if user and user.api_key:
            # Fetch available models from API
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    response = await client.get(
                        f"{API_BASE_URL}/v1/models",
                        headers={"Authorization": f"Bearer {user.api_key}"},
                    )
                    response.raise_for_status()
                    models_data = response.json()
                    available_models = [m["id"] for m in models_data.get("data", [])]
            except Exception as e:
                logger.error(f"Failed to fetch models: {e}")
                available_models = []

            if not available_models:
                await query.edit_message_text(
                    "Failed to fetch available models. Please try again.",
                    reply_markup=after_response_keyboard(),
                )
                return

            current_model = user.model or DEFAULT_MODEL
            await query.edit_message_text(
                f"Current model: {current_model}\n\nSelect a model:",
                reply_markup=model_picker_keyboard(available_models, current_model),
            )

    elif data == "change_api_key":
        context.user_data["awaiting_api_key"] = True
        from .keyboards import cancel_keyboard
        await query.edit_message_text(
            "Send your new API key:",
            reply_markup=cancel_keyboard(),
        )

    elif data == "cancel":
        context.user_data["awaiting_api_key"] = False
        await query.edit_message_text("Cancelled.", reply_markup=after_response_keyboard())

    elif data.startswith("select_model:"):
        model = data.split(":", 1)[1]
        user = users.get_user_by_telegram_id(telegram_id)
        if user:
            users.set_model(user.user_id, model)
        await query.edit_message_text(f"Model changed to {model}", reply_markup=after_response_keyboard())

    elif data.startswith("render_refresh:") or data.startswith("render:"):
        render_id = data.split(":", 1)[1]
        user = users.get_user_by_telegram_id(telegram_id)
        if user and user.api_key:
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    response = await client.get(
                        f"{API_BASE_URL}/api/renders/{render_id}",
                        headers={"Authorization": f"Bearer {user.api_key}"},
                    )
                    response.raise_for_status()
                    render = response.json()

                state = render.get("state", "unknown")
                result_url = render.get("result_url")
                error = render.get("error")
                meta = render.get("meta") or {}
                template = meta.get("template") if isinstance(meta, dict) else "render"

                state_emoji = {"pending": "⏳", "queued": "⏳", "running": "🔄", "completed": "✅", "failed": "❌"}
                emoji = state_emoji.get(state, "❓")

                text = f"{emoji} **{template}**\n\nStatus: {state}"
                if result_url:
                    text += f"\n\n[View Result]({result_url})"
                if error:
                    text += f"\n\nError: {error}"

                from .keyboards import render_detail_keyboard
                await query.edit_message_text(
                    text,
                    reply_markup=render_detail_keyboard(render_id),
                    parse_mode="Markdown",
                )
            except Exception as e:
                logger.error(f"Failed to fetch render {render_id}: {e}")
                await query.edit_message_text(
                    f"Failed to fetch render details.",
                    reply_markup=after_response_keyboard(),
                )

    elif data == "retry":
        # Retry the last user message
        user = users.get_user_by_telegram_id(telegram_id)
        if not user or not user.api_key:
            return

        chat = chats.get_or_create_current_chat(user.user_id)
        chat_messages = chats.get_messages(chat.id)

        # Find the last user message
        last_user_msg = None
        for m in reversed(chat_messages):
            if m["role"] == "user" and m["status"] == "complete":
                last_user_msg = m
                break

        if not last_user_msg:
            await query.edit_message_text("No message to retry.", reply_markup=after_response_keyboard())
            return

        # Remove the error message markup
        await query.edit_message_reply_markup(reply_markup=None)

        # Send typing indicator
        await query.message.chat.send_action("typing")

        # Build messages for retry
        model = user.model or DEFAULT_MODEL
        system_prompt = build_system_prompt(model=model)
        messages = [{"role": "system", "content": system_prompt}]
        for m in chat_messages:
            if m["status"] == "complete":
                messages.append({"role": m["role"], "content": m["content"]})

        async def send_msg(text, **kwargs):
            return await query.message.reply_text(text, **kwargs)

        async def edit_msg(msg, text, **kwargs):
            await msg.edit_text(text, **kwargs)

        output = TelegramOutput(send_msg, edit_msg)
        model = user.model or DEFAULT_MODEL
        notify_url = get_notify_url(user.webhook_secret)

        final_response = await handle_stream_with_confirmation(
            output=output,
            user=user,
            model=model,
            messages=messages,
            chat=chat,
            notify_url=notify_url,
        )

        if final_response is None:
            return

        response_msg = await output.finalize(final_response, reply_markup=after_response_keyboard())

        chats.add_message(
            user_id=user.user_id,
            chat_id=chat.id,
            role="assistant",
            content=final_response,
            telegram_message_id=response_msg.message_id,
        )


async def upload_telegram_photo(bot, file_id: str, api_key: str, telegram_id: int) -> tuple[str, str] | None:
    """Download photo from Telegram and upload to backend, return (file_id, s3_url)."""
    try:
        # Get file info from Telegram
        file = await bot.get_file(file_id)

        # Download bytes from Telegram (file.file_path is full URL with token)
        async with httpx.AsyncClient() as client:
            response = await client.get(file.file_path)
            response.raise_for_status()
            file_bytes = response.content

        # Upload to backend using SDK
        http = AsyncHTTPClient(API_BASE_URL, api_key)
        files = AsyncFiles(http)
        result = await files.upload_bytes(
            file_bytes,
            "photo.jpg",
            "image/jpeg",
            path=f"telegram/{telegram_id}",
        )
        return (result.id, result.url)
    except Exception as e:
        logger.error(f"Failed to upload photo: {e}")
        return None


async def upload_telegram_audio(bot, file_id: str, api_key: str, telegram_id: int, mime_type: str = "audio/mpeg") -> tuple[str, str] | None:
    """Download audio from Telegram and upload to backend, return (file_id, s3_url)."""
    try:
        # Get file info from Telegram
        file = await bot.get_file(file_id)

        # Download bytes from Telegram
        async with httpx.AsyncClient() as client:
            response = await client.get(file.file_path)
            response.raise_for_status()
            file_bytes = response.content

        # Determine extension from mime type
        ext_map = {
            "audio/mpeg": "mp3",
            "audio/mp3": "mp3",
            "audio/ogg": "ogg",
            "audio/wav": "wav",
            "audio/x-wav": "wav",
            "audio/mp4": "m4a",
            "audio/m4a": "m4a",
        }
        ext = ext_map.get(mime_type, "mp3")
        filename = f"audio.{ext}"

        # Upload to backend using SDK
        http = AsyncHTTPClient(API_BASE_URL, api_key)
        files = AsyncFiles(http)
        result = await files.upload_bytes(
            file_bytes,
            filename,
            mime_type,
            path=f"telegram/{telegram_id}",
        )
        return (result.id, result.url)
    except Exception as e:
        logger.error(f"Failed to upload audio: {e}")
        return None


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming photo messages - upload to backend and process with LLM."""
    if not update.message or not update.message.photo:
        return

    telegram_id = update.effective_chat.id
    caption = update.message.caption or ""
    photos = update.message.photo  # List of PhotoSize objects (different resolutions)

    # Get or create user
    user = users.get_user_by_telegram_id(telegram_id)
    if not user or not user.api_key:
        await update.message.reply_text(
            "Please set your API key first using the Menu → Set API Key option.",
            reply_markup=welcome_keyboard(),
        )
        return

    # Send typing indicator
    await update.effective_chat.send_action("typing")

    logger.info(f"Photo message from {telegram_id}: {len(photos)} sizes, caption: {caption[:50] if caption else '(none)'}")

    # Upload all photos (get largest resolution for each)
    # For a single photo, photos contains multiple sizes of the same image
    # For multiple photos sent together, this handler is called once per photo
    largest_photo = photos[-1]  # Largest resolution

    upload_result = await upload_telegram_photo(context.bot, largest_photo.file_id, user.api_key, telegram_id)
    if not upload_result:
        await update.message.reply_text("Failed to process image. Please try again.")
        return

    file_id, s3_url = upload_result
    logger.info(f"Uploaded photo: file_id={file_id}, url={s3_url}")

    # Build message with both file_id and URL (LLM can use either for tools)
    if caption:
        content = f"{caption}\n\n[Image: file_id={file_id} url={s3_url}]"
    else:
        content = f"User sent an image.\n\n[Image: file_id={file_id} url={s3_url}]"

    # Get or create chat and build messages
    chat = chats.get_or_create_current_chat(user.user_id)
    chat_messages = chats.get_messages(chat.id)

    model = user.model or DEFAULT_MODEL
    system_prompt = build_system_prompt(model=model)
    messages = [{"role": "system", "content": system_prompt}]
    for m in chat_messages:
        if m["status"] == "complete":
            messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": content})

    # Store user message with image URL annotation for history
    chats.add_message(
        user_id=user.user_id,
        chat_id=chat.id,
        role="user",
        content=content,
        telegram_message_id=update.message.message_id,
    )

    # Setup output
    async def send_msg(text, **kwargs):
        return await update.message.reply_text(text, **kwargs)

    async def edit_msg(msg, text, **kwargs):
        await msg.edit_text(text, **kwargs)

    output = TelegramOutput(send_msg, edit_msg)
    model = user.model or DEFAULT_MODEL
    notify_url = get_notify_url(user.webhook_secret)

    final_response = await handle_stream_with_confirmation(
        output=output,
        user=user,
        model=model,
        messages=messages,
        chat=chat,
        notify_url=notify_url,
    )

    if final_response is None:
        return

    # Finalize and store - ensure we never send an empty message
    if not final_response or not final_response.strip():
        final_response = "I processed your request but have no response to show."
    response_msg = await output.finalize(final_response, reply_markup=after_response_keyboard())

    chats.add_message(
        user_id=user.user_id,
        chat_id=chat.id,
        role="assistant",
        content=final_response,
        telegram_message_id=response_msg.message_id,
    )


async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming audio file messages - upload to backend and process with LLM."""
    if not update.message or not update.message.audio:
        return

    telegram_id = update.effective_chat.id
    caption = update.message.caption or ""
    audio = update.message.audio

    # Get or create user
    user = users.get_user_by_telegram_id(telegram_id)
    if not user or not user.api_key:
        await update.message.reply_text(
            "Please set your API key first using the Menu → Set API Key option.",
            reply_markup=welcome_keyboard(),
        )
        return

    # Send typing indicator
    await update.effective_chat.send_action("typing")

    logger.info(f"Audio message from {telegram_id}: {audio.file_name or 'unnamed'}, mime: {audio.mime_type}")

    # Upload audio
    mime_type = audio.mime_type or "audio/mpeg"
    upload_result = await upload_telegram_audio(context.bot, audio.file_id, user.api_key, telegram_id, mime_type)
    if not upload_result:
        await update.message.reply_text("Failed to process audio. Please try again.")
        return

    file_id, s3_url = upload_result
    logger.info(f"Uploaded audio: file_id={file_id}, url={s3_url}")

    # Build message with both file_id and URL
    if caption:
        content = f"{caption}\n\n[Audio: file_id={file_id} url={s3_url}]"
    else:
        content = f"User sent an audio file.\n\n[Audio: file_id={file_id} url={s3_url}]\n\nTo create a lip-sync speaking video, I also need an image of a face. Please send an image, or let me know what you'd like to do with this audio."

    # Get or create chat and build messages
    chat = chats.get_or_create_current_chat(user.user_id)
    chat_messages = chats.get_messages(chat.id)

    model = user.model or DEFAULT_MODEL
    system_prompt = build_system_prompt(model=model)
    messages = [{"role": "system", "content": system_prompt}]
    for m in chat_messages:
        if m["status"] == "complete":
            messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": content})

    # Store user message with audio URL annotation for history
    chats.add_message(
        user_id=user.user_id,
        chat_id=chat.id,
        role="user",
        content=content,
        telegram_message_id=update.message.message_id,
    )

    # Setup output
    async def send_msg(text, **kwargs):
        return await update.message.reply_text(text, **kwargs)

    async def edit_msg(msg, text, **kwargs):
        await msg.edit_text(text, **kwargs)

    output = TelegramOutput(send_msg, edit_msg)
    model = user.model or DEFAULT_MODEL
    notify_url = get_notify_url(user.webhook_secret)

    final_response = await handle_stream_with_confirmation(
        output=output,
        user=user,
        model=model,
        messages=messages,
        chat=chat,
        notify_url=notify_url,
    )

    if final_response is None:
        return

    # Finalize and store - ensure we never send an empty message
    if not final_response or not final_response.strip():
        final_response = "I processed your request but have no response to show."
    response_msg = await output.finalize(final_response, reply_markup=after_response_keyboard())

    chats.add_message(
        user_id=user.user_id,
        chat_id=chat.id,
        role="assistant",
        content=final_response,
        telegram_message_id=response_msg.message_id,
    )


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming voice messages - upload to backend and process with LLM."""
    if not update.message or not update.message.voice:
        return

    telegram_id = update.effective_chat.id
    voice = update.message.voice

    # Get or create user
    user = users.get_user_by_telegram_id(telegram_id)
    if not user or not user.api_key:
        await update.message.reply_text(
            "Please set your API key first using the Menu → Set API Key option.",
            reply_markup=welcome_keyboard(),
        )
        return

    # Send typing indicator
    await update.effective_chat.send_action("typing")

    logger.info(f"Voice message from {telegram_id}: duration={voice.duration}s, mime={voice.mime_type}")

    # Upload voice (Telegram voice messages are OGG/Opus)
    mime_type = voice.mime_type or "audio/ogg"
    upload_result = await upload_telegram_audio(context.bot, voice.file_id, user.api_key, telegram_id, mime_type)
    if not upload_result:
        await update.message.reply_text("Failed to process voice message. Please try again.")
        return

    file_id, s3_url = upload_result
    logger.info(f"Uploaded voice: file_id={file_id}, url={s3_url}")

    # Build message with both file_id and URL
    content = f"User sent a voice message.\n\n[Audio: file_id={file_id} url={s3_url}]\n\nTo create a lip-sync speaking video, I also need an image of a face. Please send an image, or let me know what you'd like to do with this audio."

    # Get or create chat and build messages
    chat = chats.get_or_create_current_chat(user.user_id)
    chat_messages = chats.get_messages(chat.id)

    model = user.model or DEFAULT_MODEL
    system_prompt = build_system_prompt(model=model)
    messages = [{"role": "system", "content": system_prompt}]
    for m in chat_messages:
        if m["status"] == "complete":
            messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": content})

    # Store user message with audio URL annotation for history
    chats.add_message(
        user_id=user.user_id,
        chat_id=chat.id,
        role="user",
        content=content,
        telegram_message_id=update.message.message_id,
    )

    # Setup output
    async def send_msg(text, **kwargs):
        return await update.message.reply_text(text, **kwargs)

    async def edit_msg(msg, text, **kwargs):
        await msg.edit_text(text, **kwargs)

    output = TelegramOutput(send_msg, edit_msg)
    model = user.model or DEFAULT_MODEL
    notify_url = get_notify_url(user.webhook_secret)

    final_response = await handle_stream_with_confirmation(
        output=output,
        user=user,
        model=model,
        messages=messages,
        chat=chat,
        notify_url=notify_url,
    )

    if final_response is None:
        return

    # Finalize and store - ensure we never send an empty message
    if not final_response or not final_response.strip():
        final_response = "I processed your request but have no response to show."
    response_msg = await output.finalize(final_response, reply_markup=after_response_keyboard())

    chats.add_message(
        user_id=user.user_id,
        chat_id=chat.id,
        role="assistant",
        content=final_response,
        telegram_message_id=response_msg.message_id,
    )
