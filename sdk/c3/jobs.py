"""Jobs API"""
import base64
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Iterator

if TYPE_CHECKING:
    from .http import HTTPClient


@dataclass
class Job:
    job_id: str
    job_key: str
    state: str
    gpu_type: str
    gpu_count: int
    region: str
    interruptible: bool
    price_per_hour: float
    price_per_second: float
    docker_image: str
    runtime: int
    hostname: str | None = None
    created_at: float | None = None
    started_at: float | None = None
    completed_at: float | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "Job":
        return cls(
            job_id=data.get("job_id", ""),
            job_key=data.get("job_key", ""),
            state=data.get("state", ""),
            gpu_type=data.get("gpu_type", ""),
            gpu_count=data.get("gpu_count", 1),
            region=data.get("region", ""),
            interruptible=data.get("interruptible", True),
            price_per_hour=data.get("price_per_hour", 0),
            price_per_second=data.get("price_per_second", 0),
            docker_image=data.get("docker_image", ""),
            runtime=data.get("runtime", 0),
            hostname=data.get("hostname"),
            created_at=data.get("created_at"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
        )


@dataclass
class GPUMetrics:
    index: int
    name: str
    utilization: float
    memory_used: float
    memory_total: float
    temperature: int
    power_draw: float

    @classmethod
    def from_dict(cls, data: dict) -> "GPUMetrics":
        return cls(
            index=data.get("index", 0),
            name=data.get("name", ""),
            utilization=data.get("utilization_gpu_percent", 0),
            memory_used=data.get("memory_used_mb", 0),
            memory_total=data.get("memory_total_mb", 0),
            temperature=data.get("temperature_c", 0),
            power_draw=data.get("power_draw_w", 0),
        )


@dataclass
class SystemMetrics:
    cpu_percent: float
    memory_used: float
    memory_limit: float

    @classmethod
    def from_dict(cls, data: dict) -> "SystemMetrics":
        return cls(
            cpu_percent=data.get("cpu_percent", 0),
            memory_used=data.get("memory_used_mb", 0),
            memory_limit=data.get("memory_limit_mb", 0),
        )


@dataclass
class JobMetrics:
    gpus: list[GPUMetrics] = field(default_factory=list)
    system: SystemMetrics | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "JobMetrics":
        system_data = data.get("system")
        return cls(
            gpus=[GPUMetrics.from_dict(g) for g in data.get("gpus", [])],
            system=SystemMetrics.from_dict(system_data) if system_data else None,
        )


class Jobs:
    """Jobs API wrapper"""

    def __init__(self, http: "HTTPClient"):
        self._http = http

    def list(self, state: str = None) -> list[Job]:
        """List all jobs"""
        params = {"state": state} if state else None
        data = self._http.get("/api/jobs", params=params)
        return [Job.from_dict(j) for j in data]

    def get(self, job_id: str) -> Job:
        """Get job details"""
        data = self._http.get(f"/api/jobs/{job_id}")
        return Job.from_dict(data)

    def create(
        self,
        image: str,
        command: str = None,
        gpu_type: str = "l40s",
        gpu_count: int = 1,
        region: str = None,
        runtime: int = None,
        interruptible: bool = True,
        env: dict[str, str] = None,
        ports: dict[str, int] = None,
    ) -> Job:
        """Create a new job"""
        payload = {
            "docker_image": image,
            "gpu_type": gpu_type,
            "gpu_count": gpu_count,
            "interruptible": interruptible,
            "command": base64.b64encode((command or "").encode()).decode(),
        }
        if region:
            payload["region"] = region
        if runtime:
            payload["runtime"] = runtime
        if env:
            payload["env_vars"] = env
        if ports:
            payload["ports"] = ports

        data = self._http.post("/api/jobs", json=payload)
        return Job.from_dict(data)

    def cancel(self, job_id: str) -> dict:
        """Cancel a job"""
        return self._http.delete(f"/api/jobs/{job_id}")

    def extend(self, job_id: str, runtime: int) -> Job:
        """Extend job runtime"""
        data = self._http.patch(f"/api/jobs/{job_id}", json={"runtime": runtime})
        return Job.from_dict(data)

    def logs(self, job_id: str) -> str:
        """Get job logs"""
        data = self._http.get(f"/api/jobs/{job_id}/logs")
        return data.get("logs", "")

    def metrics(self, job_id: str) -> JobMetrics:
        """Get job GPU metrics"""
        data = self._http.get(f"/api/jobs/{job_id}/metrics")
        return JobMetrics.from_dict(data)

    def token(self, job_id: str) -> str:
        """Get job auth token"""
        data = self._http.get(f"/api/jobs/{job_id}/token")
        return data.get("token", "")
