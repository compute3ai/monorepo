"""Base job class for GPU workloads"""
import time
import httpx
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..client import C3
    from ..jobs import Job


class BaseJob:
    """Base class for managed GPU jobs with lifecycle helpers"""

    DEFAULT_IMAGE: str = ""
    DEFAULT_GPU_TYPE: str = "l40s"
    HEALTH_ENDPOINT: str = "/"
    HEALTH_TIMEOUT: float = 5.0

    def __init__(self, c3: "C3", job: "Job"):
        self.c3 = c3
        self.job = job
        self._base_url: str | None = None

    @property
    def job_id(self) -> str:
        return self.job.job_id

    @property
    def hostname(self) -> str | None:
        return self.job.hostname

    @property
    def base_url(self) -> str:
        """Base URL - only valid after job is running"""
        if not self._base_url and self.hostname:
            self._base_url = f"http://{self.hostname}"
        return self._base_url or ""

    @property
    def auth_headers(self) -> dict:
        """Headers for authenticated requests. Override in subclasses for custom auth."""
        return {"Authorization": f"Bearer {self.c3._api_key}"}

    @classmethod
    def get_running(cls, c3: "C3", image_filter: str = None) -> "BaseJob | None":
        """Find an existing running job, optionally filtering by image"""
        jobs = c3.jobs.list(state="running")
        for job in jobs:
            if image_filter and image_filter not in job.docker_image:
                continue
            return cls(c3, job)
        return None

    @classmethod
    def get_by_instance(cls, c3: "C3", instance: str, state: str = "running") -> "BaseJob":
        """Get a job by ID, hostname, or IP address.

        Args:
            c3: C3 client
            instance: Job ID (UUID), hostname (partial match), or IP address
            state: State filter for hostname/IP search (default: running)

        Returns:
            Job wrapper instance

        Raises:
            ValueError: If no matching job found
        """
        from ..jobs import find_job

        job = find_job(c3.jobs, instance, state=state)
        if not job:
            raise ValueError(f"No job found matching: {instance}")
        return cls(c3, job)

    @classmethod
    def create(
        cls,
        c3: "C3",
        image: str = None,
        gpu_type: str = None,
        gpu_count: int = 1,
        runtime: int = 3600,
        **kwargs,
    ) -> "BaseJob":
        """Create a new job"""
        job = c3.jobs.create(
            image=image or cls.DEFAULT_IMAGE,
            gpu_type=gpu_type or cls.DEFAULT_GPU_TYPE,
            gpu_count=gpu_count,
            runtime=runtime,
            **kwargs,
        )
        return cls(c3, job)

    @classmethod
    def get_or_create(
        cls,
        c3: "C3",
        image: str = None,
        gpu_type: str = None,
        gpu_count: int = 1,
        runtime: int = 3600,
        reuse: bool = True,
        **kwargs,
    ) -> "BaseJob":
        """Get existing running job or create new one"""
        if reuse:
            existing = cls.get_running(c3, image_filter=image or cls.DEFAULT_IMAGE)
            if existing:
                return existing

        return cls.create(
            c3,
            image=image,
            gpu_type=gpu_type,
            gpu_count=gpu_count,
            runtime=runtime,
            **kwargs,
        )

    def refresh(self) -> "BaseJob":
        """Refresh job state from API"""
        self.job = self.c3.jobs.get(self.job_id)
        self._base_url = None
        return self

    def wait_for_running(self, timeout: float = 300, poll_interval: float = 5) -> bool:
        """Wait for job to reach running state via API polling.

        IMPORTANT: Do not attempt to connect to hostname until this returns True.
        Connecting before the job is running will cache NXDOMAIN in DNS for ~30 mins.
        """
        start = time.time()
        while time.time() - start < timeout:
            self.refresh()
            if self.job.state == "running" and self.hostname:
                return True
            if self.job.state in ("failed", "cancelled", "completed", "terminated"):
                return False
            time.sleep(poll_interval)
        return False

    def wait_for_hostname(self, timeout: float = 300, poll_interval: float = 5) -> bool:
        """Alias for wait_for_running - waits for job to be running with hostname"""
        return self.wait_for_running(timeout=timeout, poll_interval=poll_interval)

    def check_health(self) -> bool:
        """Check if the service is responding.

        Only call this after job is confirmed running via wait_for_running().
        """
        if not self.base_url or self.job.state != "running":
            return False
        try:
            with httpx.Client(timeout=self.HEALTH_TIMEOUT) as client:
                resp = client.get(
                    f"{self.base_url}{self.HEALTH_ENDPOINT}",
                    headers=self.auth_headers,
                )
                return resp.status_code == 200
        except Exception:
            return False

    def wait_ready(
        self, timeout: float = 300, poll_interval: float = 10
    ) -> bool:
        """Wait for job to be ready (running state + health check passing).

        First waits for job to reach running state via API polling,
        then checks health endpoint. This prevents DNS NXDOMAIN caching.
        """
        start = time.time()

        # First wait for running state via API (no HTTP to hostname yet)
        if not self.wait_for_running(timeout=timeout, poll_interval=poll_interval):
            return False

        # Now job is running, safe to check health endpoint
        elapsed = time.time() - start
        remaining = timeout - elapsed
        while remaining > 0:
            if self.check_health():
                return True
            time.sleep(poll_interval)
            remaining = timeout - (time.time() - start)
        return False

    def shutdown(self) -> dict:
        """Cancel the job"""
        return self.c3.jobs.cancel(self.job_id)

    def extend(self, runtime: int) -> "BaseJob":
        """Extend job runtime"""
        self.job = self.c3.jobs.extend(self.job_id, runtime=runtime)
        return self
