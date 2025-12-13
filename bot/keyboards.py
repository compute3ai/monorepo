"""
Inline keyboard builders for the bot.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def after_response_keyboard() -> InlineKeyboardMarkup:
    """Keyboard shown after each AI response."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 New Context", callback_data="new_context"),
            InlineKeyboardButton("☰ Menu", callback_data="menu"),
        ]
    ])


def menu_keyboard() -> InlineKeyboardMarkup:
    """Main menu keyboard."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🖼️ Renders", callback_data="renders")],
        [InlineKeyboardButton("🤖 Change Model", callback_data="change_model")],
        [InlineKeyboardButton("🔑 Change API Key", callback_data="change_api_key")],
        [InlineKeyboardButton("« Back", callback_data="back")],
    ])


# Keep old name for backwards compatibility
settings_keyboard = menu_keyboard


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


def welcome_keyboard() -> InlineKeyboardMarkup:
    """Keyboard shown on welcome message."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎁 Start for Free", callback_data="start_free")],
    ])


def obfuscate_key(api_key: str) -> str:
    """Obfuscate API key for display."""
    if not api_key:
        return "Not set"
    if len(api_key) <= 8:
        return "****"
    return f"{api_key[:4]}****{api_key[-4:]}"


def renders_list_keyboard(renders: list, page: int = 0, page_size: int = 5) -> InlineKeyboardMarkup:
    """Keyboard showing list of user renders."""
    buttons = []

    if not renders:
        buttons.append([InlineKeyboardButton("No renders yet", callback_data="noop")])
    else:
        # Status emoji mapping
        status_emoji = {
            "pending": "⏳",
            "success": "✅",
            "failed": "❌",
            "cancelled": "🚫",
        }

        for render in renders[:page_size]:
            emoji = status_emoji.get(render.status, "❓")
            # Show short render_id and template
            short_id = render.render_id[:8] if render.render_id else "?"
            template = render.template or "render"
            label = f"{emoji} {template} ({short_id})"
            buttons.append([InlineKeyboardButton(label, callback_data=f"render:{render.render_id}")])

    buttons.append([InlineKeyboardButton("« Back to Menu", callback_data="menu")])
    return InlineKeyboardMarkup(buttons)


def render_detail_keyboard(render_id: str) -> InlineKeyboardMarkup:
    """Keyboard for render detail view."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Refresh Status", callback_data=f"render_refresh:{render_id}")],
        [InlineKeyboardButton("« Back to Renders", callback_data="renders")],
    ])
