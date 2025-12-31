"""Renders API"""
from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Optional

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

    # =========================================================================
    # Flow endpoints - simplified interfaces
    # =========================================================================

    def text_to_image(self, prompt: str) -> Render:
        """Generate an image using Qwen-Image (great for text in images).

        Args:
            prompt: Text description of the image

        Example:
            render = c3.renders.text_to_image("a cat wearing sunglasses")
        """
        data = self._http.post("/api/flow/text-to-image", json={"prompt": prompt})
        return Render.from_dict(data)

    def text_to_image_hidream(self, prompt: str) -> Render:
        """Generate an image using HiDream I1 Full (highest quality).

        Args:
            prompt: Text description of the image

        Example:
            render = c3.renders.text_to_image_hidream("a mystical forest")
        """
        data = self._http.post("/api/flow/text-to-image-hidream", json={"prompt": prompt})
        return Render.from_dict(data)

    def text_to_video(self, prompt: str) -> Render:
        """Generate a video using Wan 2.2 14B.

        Args:
            prompt: Text description of the video

        Example:
            render = c3.renders.text_to_video("a cat walking through a garden")
        """
        data = self._http.post("/api/flow/text-to-video", json={"prompt": prompt})
        return Render.from_dict(data)

    def image_to_video(self, prompt: str, image_url: str) -> Render:
        """Animate an image using Wan 2.2 Animate.

        Args:
            prompt: Description of the motion/animation
            image_url: URL of the image to animate

        Example:
            render = c3.renders.image_to_video("dancing", "https://example.com/img.png")
        """
        data = self._http.post(
            "/api/flow/image-to-video",
            json={"prompt": prompt, "image_url": image_url}
        )
        return Render.from_dict(data)

    def speaking_video(self, prompt: str, image_url: str, audio_url: str) -> Render:
        """Generate a lip-sync video using HuMo.

        Args:
            prompt: Description of the scene/character
            image_url: URL of the face/character image
            audio_url: URL of the audio/speech file

        Example:
            render = c3.renders.speaking_video(
                "A person talking to camera",
                "https://example.com/face.png",
                "https://example.com/speech.mp3"
            )
        """
        data = self._http.post(
            "/api/flow/speaking-video",
            json={"prompt": prompt, "image_url": image_url, "audio_url": audio_url}
        )
        return Render.from_dict(data)

    def speaking_video_wan(self, prompt: str, image_url: str, audio_url: str) -> Render:
        """Generate an audio-driven video using Wan 2.2 S2V.

        Args:
            prompt: Description of the scene/action
            image_url: URL of the image
            audio_url: URL of the audio file

        Example:
            render = c3.renders.speaking_video_wan(
                "The person is singing",
                "https://example.com/face.png",
                "https://example.com/song.mp3"
            )
        """
        data = self._http.post(
            "/api/flow/speaking-video-wan",
            json={"prompt": prompt, "image_url": image_url, "audio_url": audio_url}
        )
        return Render.from_dict(data)

    def image_to_image(
        self,
        prompt: str,
        image_urls: List[str],
    ) -> Render:
        """Transform images using Qwen Image Edit with 1-3 input images.

        Args:
            prompt: Description of the transformation
            image_urls: List of 1-3 image URLs (first is main, others are references)

        Example:
            render = c3.renders.image_to_image(
                "Apply the artistic style from the references",
                [
                    "https://example.com/subject.jpg",
                    "https://example.com/style1.jpg",
                    "https://example.com/style2.jpg",
                ]
            )
        """
        data = self._http.post(
            "/api/flow/image-to-image",
            json={
                "prompt": prompt,
                "image_urls": image_urls,
            }
        )
        return Render.from_dict(data)

    def first_last_frame_video(
        self,
        prompt: str,
        start_image_url: str,
        end_image_url: str,
    ) -> Render:
        """Generate video morphing between two images using Wan 2.2.

        Args:
            prompt: Description of the transition/motion
            start_image_url: URL of the starting frame
            end_image_url: URL of the ending frame

        Example:
            render = c3.renders.first_last_frame_video(
                "smooth transition from day to night",
                "https://example.com/day.png",
                "https://example.com/night.png"
            )
        """
        data = self._http.post(
            "/api/flow/first-last-frame-video",
            json={
                "prompt": prompt,
                "start_image_url": start_image_url,
                "end_image_url": end_image_url,
            }
        )
        return Render.from_dict(data)
