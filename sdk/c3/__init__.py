"""C3 SDK - Python client for Compute3 API"""
from .client import C3
from .config import configure
from .http import APIError
from .instances import GPUType, GPUConfig, Region, GPUPricing, PricingTier
from .jobs import Job, JobMetrics, GPUMetrics

__version__ = "0.1.0"
__all__ = [
    "C3",
    "configure",
    "APIError",
    # Instance types
    "GPUType",
    "GPUConfig",
    "Region",
    "GPUPricing",
    "PricingTier",
    # Jobs
    "Job",
    "JobMetrics",
    "GPUMetrics",
]
