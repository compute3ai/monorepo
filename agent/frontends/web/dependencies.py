"""
FastAPI dependencies for authentication.
"""

from fastapi import Header, HTTPException

from services import users


async def require_api_key(
    x_api_key: str = Header(None, alias="X-API-KEY"),
    authorization: str = Header(None, alias="Authorization"),
) -> str:
    """
    Dependency to require API key authentication. Returns user_id.

    Accepts API key via:
    - X-API-KEY header
    - Authorization: Bearer <api_key> header
    """
    api_key = x_api_key

    # Try Bearer token if no X-API-KEY
    if not api_key and authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            api_key = parts[1]

    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Provide X-API-KEY or Authorization header",
        )

    # Look up user by API key
    from db.models import get_session, User

    with get_session() as session:
        user = session.query(User).filter(User.api_key == api_key).first()
        if not user:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return user.user_id
