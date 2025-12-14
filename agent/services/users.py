"""
User service - user management functions.
"""

from config import DEFAULT_MODEL
from db.models import get_session, User


def get_user(user_id: str) -> User | None:
    """Get user by user_id."""
    with get_session() as session:
        user = session.query(User).filter(User.user_id == user_id).first()
        if user:
            session.expunge(user)
        return user


def get_user_by_telegram_id(telegram_id: int) -> User | None:
    """Get user by Telegram ID."""
    with get_session() as session:
        user = session.query(User).filter(User.telegram_id == telegram_id).first()
        if user:
            session.expunge(user)
        return user


def create_user(
    user_id: str,
    telegram_id: int | None = None,
    api_key: str | None = None,
) -> User:
    """Create a new user."""
    with get_session() as session:
        user = User(
            user_id=user_id,
            telegram_id=telegram_id,
            api_key=api_key,
            model=DEFAULT_MODEL,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        session.expunge(user)
        return user


def get_or_create_user(user_id: str) -> User:
    """Get or create user by user_id."""
    user = get_user(user_id)
    if not user:
        user = create_user(user_id)
    return user


def get_or_create_telegram_user(telegram_id: int) -> User:
    """Get or create user by Telegram ID."""
    user = get_user_by_telegram_id(telegram_id)
    if not user:
        user_id = f"tg_{telegram_id}"
        user = create_user(user_id, telegram_id)
    return user


def set_api_key(user_id: str, api_key: str) -> None:
    """Set user's API key."""
    with get_session() as session:
        user = session.query(User).filter(User.user_id == user_id).first()
        if user:
            user.api_key = api_key


def set_model(user_id: str, model: str) -> None:
    """Set user's model preference."""
    with get_session() as session:
        user = session.query(User).filter(User.user_id == user_id).first()
        if user:
            user.model = model


def clear_api_key(user_id: str) -> None:
    """Clear user's API key."""
    with get_session() as session:
        user = session.query(User).filter(User.user_id == user_id).first()
        if user:
            user.api_key = None


def set_free_account(user_id: str, jwt_token: str) -> None:
    """Set user's free account JWT token."""
    with get_session() as session:
        user = session.query(User).filter(User.user_id == user_id).first()
        if user:
            user.api_key = jwt_token
            user.free = 1


def get_user_by_webhook_secret(webhook_secret: str) -> User | None:
    """Get user by webhook secret."""
    with get_session() as session:
        user = session.query(User).filter(User.webhook_secret == webhook_secret).first()
        if user:
            session.expunge(user)
        return user
