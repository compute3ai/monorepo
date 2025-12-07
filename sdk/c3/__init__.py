"""C3 SDK - Python client for Compute3 API"""
from .client import C3
from .config import configure, GHCR_IMAGES, COMFYUI_IMAGE
from .http import APIError
from .instances import GPUType, GPUConfig, Region, GPUPricing, PricingTier
from .jobs import Job, JobMetrics, GPUMetrics, find_job, find_by_id, find_by_hostname, find_by_ip
from .renders import Render, RenderStatus
from .job import BaseJob, ComfyUIJob, apply_params, find_node, find_nodes, load_template, graph_to_api, DEFAULT_OBJECT_INFO
from .logs import LogStream, stream_logs, fetch_logs

__version__ = "0.2.1"
__all__ = [
    "C3",
    "configure",
    "APIError",
    # Images
    "GHCR_IMAGES",
    "COMFYUI_IMAGE",
    # Instance types
    "GPUType",
    "GPUConfig",
    "Region",
    "GPUPricing",
    "PricingTier",
    # Jobs API
    "Job",
    "JobMetrics",
    "GPUMetrics",
    # Renders API
    "Render",
    "RenderStatus",
    # Job lookup utils
    "find_job",
    "find_by_id",
    "find_by_hostname",
    "find_by_ip",
    # Job helpers
    "BaseJob",
    "ComfyUIJob",
    # Workflow utils
    "apply_params",
    "find_node",
    "find_nodes",
    "load_template",
    "graph_to_api",
    "DEFAULT_OBJECT_INFO",
    # Log streaming
    "LogStream",
    "stream_logs",
    "fetch_logs",
]
