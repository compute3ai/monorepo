"""User API"""
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .http import HTTPClient


@dataclass
class User:
    user_id: str
    email: str | None
    name: str | None
    is_active: bool
    created_at: str

    @classmethod
    def from_dict(cls, data: dict) -> "User":
        return cls(
            user_id=data.get("user_id", ""),
            email=data.get("email"),
            name=data.get("name"),
            is_active=data.get("is_active", True),
            created_at=data.get("created_at", ""),
        )


class UserAPI:
    """User API wrapper"""

    def __init__(self, http: "HTTPClient"):
        self._http = http

    def get(self) -> User:
        """Get current user info"""
        data = self._http.get("/api/user")
        return User.from_dict(data)
