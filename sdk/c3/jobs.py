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
    cpu_cores: float
    cpu_unix_percent: float
    memory_used: float
    memory_limit: float

    @classmethod
    def from_dict(cls, data: dict) -> "SystemMetrics":
        return cls(
            cpu_percent=data.get("cpu_percent", 0),
            cpu_cores=data.get("cpu_cores", 1),
            cpu_unix_percent=data.get("cpu_unix_percent", data.get("cpu_percent", 0)),
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
        auth: bool = False,
    ) -> Job:
        """Create a new job.

        Args:
            image: Docker image to run
            command: Command to execute (base64 encoded internally)
            gpu_type: GPU type (e.g., "l40s", "a100")
            gpu_count: Number of GPUs
            region: Region to run in
            runtime: Max runtime in seconds
            interruptible: Allow spot/preemptible instances
            env: Environment variables
            ports: Ports to expose. Use {"lb": port} for HTTPS load balancer
            auth: Enable Bearer token auth on load balancer (use with ports={"lb": port})
        """
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
        if auth:
            payload["auth"] = auth

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


# Utility functions for finding jobs


def is_uuid(s: str) -> bool:
    """Check if string looks like a UUID (job ID)"""
    return "-" in s and len(s) > 30


def find_by_id(jobs: Jobs, job_id: str) -> Job | None:
    """Find job by UUID via direct API call.

    Args:
        jobs: Jobs API instance
        job_id: Full job UUID

    Returns:
        Job if found, None if not found or error
    """
    try:
        return jobs.get(job_id)
    except Exception:
        return None


def find_by_hostname(job_list: list[Job], hostname: str) -> Job | None:
    """Find job by hostname (exact or prefix match).

    Args:
        job_list: List of Job objects to search
        hostname: Hostname to match (can be partial prefix)

    Returns:
        First matching Job or None
    """
    for job in job_list:
        if job.hostname and (job.hostname == hostname or job.hostname.startswith(hostname)):
            return job
    return None


def find_by_ip(job_list: list[Job], ip: str) -> Job | None:
    """Find job by IP address (extracted from hostname).

    Args:
        job_list: List of Job objects to search
        ip: IP address to match

    Returns:
        First matching Job or None
    """
    import socket

    for job in job_list:
        if not job.hostname:
            continue
        try:
            job_ip = socket.gethostbyname(job.hostname)
            if job_ip == ip:
                return job
        except socket.gaierror:
            continue
    return None


def find_job(jobs: Jobs, identifier: str, state: str = None) -> Job | None:
    """Find a job by UUID, hostname, or IP address.

    Args:
        jobs: Jobs API instance
        identifier: Job UUID, hostname (partial match), or IP address
        state: Optional state filter for listing jobs

    Returns:
        Matching Job or None
    """
    # Try UUID first (direct API call)
    if is_uuid(identifier):
        return find_by_id(jobs, identifier)

    # Get job list for hostname/IP search
    job_list = jobs.list(state=state)

    # Try hostname match
    job = find_by_hostname(job_list, identifier)
    if job:
        return job

    # Try IP match (slower, requires DNS lookup)
    return find_by_ip(job_list, identifier)
