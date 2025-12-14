"""
Telegram inline keyboard builders.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def after_response_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 New Context", callback_data="new_context"),
            InlineKeyboardButton("☰ Menu", callback_data="menu"),
        ]
    ])


def menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🖼️ Renders", callback_data="renders")],
        [InlineKeyboardButton("🤖 Change Model", callback_data="change_model")],
        [InlineKeyboardButton("🔑 Change API Key", callback_data="change_api_key")],
        [InlineKeyboardButton("« Back", callback_data="back")],
    ])


def model_picker_keyboard(models: list[str], current_model: str) -> InlineKeyboardMarkup:
    buttons = []
    for model in models:
        prefix = "✓ " if model == current_model else ""
        buttons.append([InlineKeyboardButton(f"{prefix}{model}", callback_data=f"select_model:{model}")])
    buttons.append([InlineKeyboardButton("« Back", callback_data="settings")])
    return InlineKeyboardMarkup(buttons)


def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("« Cancel", callback_data="cancel")],
    ])


def welcome_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎁 Start for Free", callback_data="start_free")],
    ])


def renders_list_keyboard(renders: list, page_size: int = 5) -> InlineKeyboardMarkup:
    buttons = []
    if not renders:
        buttons.append([InlineKeyboardButton("No renders yet", callback_data="noop")])
    else:
        status_emoji = {"pending": "⏳", "success": "✅", "failed": "❌", "cancelled": "🚫"}
        for render in renders[:page_size]:
            emoji = status_emoji.get(render.status, "❓")
            short_id = render.render_id[:8] if render.render_id else "?"
            template = render.template or "render"
            buttons.append([InlineKeyboardButton(f"{emoji} {template} ({short_id})", callback_data=f"render:{render.render_id}")])
    buttons.append([InlineKeyboardButton("« Back to Menu", callback_data="menu")])
    return InlineKeyboardMarkup(buttons)


def render_detail_keyboard(render_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Refresh Status", callback_data=f"render_refresh:{render_id}")],
        [InlineKeyboardButton("« Back to Renders", callback_data="renders")],
    ])


def obfuscate_key(api_key: str) -> str:
    if not api_key:
        return "Not set"
    if len(api_key) <= 8:
        return "****"
    return f"{api_key[:4]}****{api_key[-4:]}"
