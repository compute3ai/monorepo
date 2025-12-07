"""
Inline keyboard builders for the bot.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def after_response_keyboard() -> InlineKeyboardMarkup:
    """Keyboard shown after each AI response."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 New Context", callback_data="new_context"),
            InlineKeyboardButton("⚙️ Settings", callback_data="settings"),
        ]
    ])


def settings_keyboard() -> InlineKeyboardMarkup:
    """Main settings keyboard."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🤖 Change Model", callback_data="change_model")],
        [InlineKeyboardButton("🔑 Change API Key", callback_data="change_api_key")],
        [InlineKeyboardButton("« Back", callback_data="back")],
    ])


def model_picker_keyboard(models: list[str], current_model: str) -> InlineKeyboardMarkup:
    """Keyboard for selecting a model."""
    buttons = []
    for model in models:
        prefix = "✓ " if model == current_model else ""
        buttons.append([InlineKeyboardButton(f"{prefix}{model}", callback_data=f"select_model:{model}")])
    buttons.append([InlineKeyboardButton("« Back", callback_data="settings")])
    return InlineKeyboardMarkup(buttons)


def cancel_keyboard() -> InlineKeyboardMarkup:
    """Cancel button for input flows."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("« Cancel", callback_data="cancel")],
    ])


def new_context_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for #NewContext marker message (no context_id)."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Resume this context", callback_data="resume_context:")],
    ])


def new_context_keyboard_with_id(context_id: str) -> InlineKeyboardMarkup:
    """Keyboard for #NewContext marker message with context_id for resume."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Resume this context", callback_data=f"resume_context:{context_id}")],
    ])


def obfuscate_key(api_key: str) -> str:
    """Obfuscate API key for display."""
    if not api_key:
        return "Not set"
    if len(api_key) <= 8:
        return "****"
    return f"{api_key[:4]}****{api_key[-4:]}"
