"""Renders API"""
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .http import HTTPClient


@dataclass
class Render:
    render_id: str
    state: str
    template: str | None = None
    render_type: str | None = None
    result_url: str | None = None
    error: str | None = None
    created_at: float | None = None
    started_at: float | None = None
    completed_at: float | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "Render":
        return cls(
            render_id=data.get("id") or data.get("render_id", ""),
            state=data.get("state", ""),
            template=data.get("template") or data.get("meta", {}).get("template"),
            render_type=data.get("type") or data.get("render_type"),
            result_url=data.get("result_url"),
            error=data.get("error"),
            created_at=data.get("created_at"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
        )


@dataclass
class RenderStatus:
    render_id: str
    state: str
    progress: float | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "RenderStatus":
        return cls(
            render_id=data.get("id") or data.get("render_id", ""),
            state=data.get("state", ""),
            progress=data.get("progress"),
        )


class Renders:
    """Renders API wrapper"""

    def __init__(self, http: "HTTPClient"):
        self._http = http

    def list(
        self,
        state: str = None,
        template: str = None,
        type: str = None,
    ) -> list[Render]:
        """List all renders.

        Args:
            state: Filter by state (e.g., "pending", "running", "completed")
            template: Filter by template name
            type: Filter by render type (e.g., "comfyui")
        """
        params = {}
        if state:
            params["state"] = state
        if template:
            params["template"] = template
        if type:
            params["type"] = type

        data = self._http.get("/api/renders", params=params or None)
        # Handle paginated response
        items = data.get("items", data) if isinstance(data, dict) else data
        return [Render.from_dict(r) for r in items]

    def get(self, render_id: str) -> Render:
        """Get render details"""
        data = self._http.get(f"/api/renders/{render_id}")
        return Render.from_dict(data)

    def create(
        self,
        params: dict,
        render_type: str = "comfyui",
        notify_url: str = None,
    ) -> Render:
        """Create a new render.

        Args:
            params: Render parameters (workflow-specific)
            render_type: Type of render (default: "comfyui")
            notify_url: Optional webhook URL for completion notification
        """
        payload = {
            "type": render_type,
            "params": params,
        }
        if notify_url:
            payload["notify_url"] = notify_url

        data = self._http.post("/api/renders", json=payload)
        return Render.from_dict(data)

    def cancel(self, render_id: str) -> dict:
        """Cancel a render"""
        return self._http.delete(f"/api/renders/{render_id}")

    def status(self, render_id: str) -> RenderStatus:
        """Get render status (lightweight polling endpoint)"""
        data = self._http.get(f"/api/renders/{render_id}/status")
        return RenderStatus.from_dict(data)
