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


def error_keyboard() -> InlineKeyboardMarkup:
    """Keyboard shown after an error occurs."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 New Context", callback_data="new_context"),
            InlineKeyboardButton("🔁 Retry", callback_data="retry"),
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
    buttons.append([InlineKeyboardButton("« Back", callback_data="back")])
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
    """Build keyboard for renders list. Accepts both ORM objects and API dicts."""
    buttons = []
    if not renders:
        buttons.append([InlineKeyboardButton("No renders yet", callback_data="noop")])
    else:
        # Map API states to emoji (API uses 'state', local DB uses 'status')
        state_emoji = {
            "pending": "⏳", "queued": "⏳", "running": "🔄",
            "completed": "✅", "success": "✅",
            "failed": "❌", "cancelled": "🚫",
        }
        for render in renders[:page_size]:
            # Support both dict (API) and ORM object formats
            if isinstance(render, dict):
                state = render.get("state", "unknown")
                render_id = render.get("id", "")
                # Try to get template from meta if available
                meta = render.get("meta") or {}
                template = meta.get("template") if isinstance(meta, dict) else None
            else:
                state = getattr(render, "status", "unknown")
                render_id = getattr(render, "render_id", "")
                template = getattr(render, "template", None)

            emoji = state_emoji.get(state, "❓")
            short_id = render_id[:8] if render_id else "?"
            label = template or state or "render"
            buttons.append([InlineKeyboardButton(f"{emoji} {label} ({short_id})", callback_data=f"render:{render_id}")])
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
