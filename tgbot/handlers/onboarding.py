"""
Onboarding handlers - welcome and API key setup.
"""

from telegram import Update
from telegram.ext import ContextTypes

from db import get_or_create_user, set_api_key
from services.compute3 import verify_api_key
from keyboards import after_response_keyboard

WELCOME_MESSAGE = """👋 <b>Welcome to the Compute3 AI Bot!</b>

To use this bot, you'll need an API key. Don't have one? No worries - grab one for free at:
🔗 https://console.compute3.ai

<i>By using this bot, you agree to our Terms of Service:</i>
🔗 https://compute3.ai/terms

<b>The TL;DR:</b> We don't store your personal data or track you. Just don't use this for anything sketchy - be excellent to each other! 🤝

Ready? Send me your API key to get started!"""


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    await show_welcome(update, context)


async def show_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show welcome message and prompt for API key."""
    chat_id = update.effective_chat.id
    get_or_create_user(chat_id)  # Ensure user exists

    await update.message.reply_text(
        WELCOME_MESSAGE,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    context.user_data["awaiting_api_key"] = True


async def handle_api_key_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Handle API key input during onboarding.
    Returns True if this was an API key input, False otherwise.
    """
    if not context.user_data.get("awaiting_api_key"):
        return False

    chat_id = update.effective_chat.id
    potential_key = update.message.text.strip()

    # Verify the key
    await update.message.reply_text("🔄 Verifying your API key...")

    user_info = await verify_api_key(potential_key)

    if user_info:
        set_api_key(chat_id, potential_key)
        context.user_data["awaiting_api_key"] = False

        name = user_info.get("name") or user_info.get("email") or "there"
        await update.message.reply_text(
            f"✅ <b>API key verified!</b>\n\n"
            f"Hello, {name}! You're all set.\n\n"
            f"Send me a message to start chatting.",
            parse_mode="HTML",
            reply_markup=after_response_keyboard(),
        )
    else:
        await update.message.reply_text(
            "❌ Invalid API key. Please try again.\n\n"
            "Make sure you're using a valid Compute3 API key.",
        )

    return True
