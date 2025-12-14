"""
Users API routes.
"""

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from frontends.web.dependencies import require_api_key
from services import users as users_service
from config import DEFAULT_MODEL

router = APIRouter(prefix="/user", tags=["user"])


# =============================================================================
# Pydantic models
# =============================================================================


class UserResponse(BaseModel):
    user_id: str
    model: str
    free: bool
    created_at: str


class UserUpdate(BaseModel):
    model: Optional[str] = None


# =============================================================================
# REST endpoints
# =============================================================================


@router.get("", response_model=UserResponse)
async def get_user(
    user_id: str = Depends(require_api_key),
):
    """Get current user info."""
    user = users_service.get_user(user_id)
    return UserResponse(
        user_id=user.user_id,
        model=user.model or DEFAULT_MODEL,
        free=bool(user.free),
        created_at=user.created_at.isoformat(),
    )


@router.patch("", response_model=UserResponse)
async def update_user(
    data: UserUpdate,
    user_id: str = Depends(require_api_key),
):
    """Update user settings."""
    if data.model:
        users_service.set_model(user_id, data.model)

    user = users_service.get_user(user_id)
    return UserResponse(
        user_id=user.user_id,
        model=user.model or DEFAULT_MODEL,
        free=bool(user.free),
        created_at=user.created_at.isoformat(),
    )
