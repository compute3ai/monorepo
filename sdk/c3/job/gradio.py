"""Gradio job helpers for GPU workloads running Gradio-based services"""
from typing import TYPE_CHECKING

from .base import BaseJob


if TYPE_CHECKING:
    from ..client import C3


class GradioJob(BaseJob):
    """Gradio-specific job with service connection helpers.

    Used for GPU workloads that expose a Gradio API (e.g., WhisperX transcription).
    Supports HTTPS load balancer with bearer token auth (same pattern as ComfyUI).
    """

    DEFAULT_GPU_TYPE = "l4"
    HEALTH_ENDPOINT = "/"
    HEALTH_TIMEOUT = 10.0
    GRADIO_PORT = 7860

    def __init__(self, c3: "C3", job, use_lb: bool = False, use_auth: bool = False):
        super().__init__(c3, job)
        self._use_lb = use_lb
        self.use_auth = use_auth
        self._job_token: str | None = None

    @property
    def use_lb(self) -> bool:
        return self._use_lb

    @use_lb.setter
    def use_lb(self, value: bool):
        self._use_lb = value
        self._base_url = None

    @property
    def base_url(self) -> str:
        """Gradio base URL - HTTPS if using lb, HTTP otherwise"""
        if not self._base_url and self.hostname:
            if self._use_lb:
                self._base_url = f"https://{self.hostname}"
            else:
                self._base_url = f"http://{self.hostname}:{self.GRADIO_PORT}"
        return self._base_url or ""

    @property
    def auth_headers(self) -> dict:
        """Headers for authenticated requests"""
        if self.use_auth:
            if not self._job_token:
                self._job_token = self.c3.jobs.token(self.job_id)
            return {"Authorization": f"Bearer {self._job_token}"}
        return super().auth_headers

    @property
    def job_token(self) -> str:
        """Get the job-specific bearer token for Gradio API auth"""
        if not self._job_token:
            self._job_token = self.c3.jobs.token(self.job_id)
        return self._job_token

    @classmethod
    def create_for_service(
        cls,
        c3: "C3",
        image: str,
        gpu_type: str = None,
        gpu_count: int = 1,
        runtime: int = 3600,
        lb: int = None,
        auth: bool = True,
        **kwargs,
    ) -> "GradioJob":
        """Create a new Gradio job for a specific Docker image.

        Args:
            c3: C3 client instance
            image: Docker image to run (e.g., "ghcr.io/comput3ai/c3-whisperx-gradio:latest")
            gpu_type: GPU type (default: l4)
            gpu_count: Number of GPUs
            runtime: Max runtime in seconds
            lb: Port for HTTPS load balancer (default: 7860). If set, uses HTTPS.
            auth: Enable Bearer token auth on load balancer (default: True)
        """
        if lb is None:
            lb = cls.GRADIO_PORT

        ports = kwargs.pop("ports", {}) or {}
        if lb:
            ports["lb"] = lb
        else:
            ports[str(cls.GRADIO_PORT)] = cls.GRADIO_PORT

        job = c3.jobs.create(
            image=image,
            gpu_type=gpu_type or cls.DEFAULT_GPU_TYPE,
            gpu_count=gpu_count,
            runtime=runtime,
            ports=ports,
            auth=auth,
            **kwargs,
        )
        return cls(c3, job, use_lb=bool(lb), use_auth=auth)

    def connect(self):
        """Return a gradio_client.Client connected to this instance.

        Requires: pip install gradio-client

        Returns:
            gradio_client.Client configured with auth headers
        """
        from gradio_client import Client

        headers = self.auth_headers if self.use_auth else {}
        return Client(self.base_url, headers=headers)
