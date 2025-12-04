"""Job helpers for different GPU workload types"""
from .base import BaseJob
from .comfyui import (
    ComfyUIJob,
    apply_params,
    find_node,
    find_nodes,
    load_template,
    graph_to_api,
    DEFAULT_OBJECT_INFO,
)

__all__ = [
    "BaseJob",
    "ComfyUIJob",
    "apply_params",
    "find_node",
    "find_nodes",
    "load_template",
    "graph_to_api",
    "DEFAULT_OBJECT_INFO",
]
