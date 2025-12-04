"""ComfyUI job helpers"""
import json
import time
import random
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx

from .base import BaseJob
from ..config import COMFYUI_IMAGE

if TYPE_CHECKING:
    from ..client import C3


# Default object_info for offline workflow conversion (no running instance needed)
# This covers common node types - extend as needed for new workflows
DEFAULT_OBJECT_INFO = {
    # Text encoders
    "CLIPTextEncode": {
        "input": {"required": {"clip": ["CLIP"], "text": ["STRING", {"multiline": True}]}, "optional": {}},
        "input_order": {"required": ["clip", "text"], "optional": []},
    },
    "CLIPLoader": {
        "input": {"required": {"clip_name": [["model.safetensors"], {}], "type": [["stable_diffusion", "wan"], {}], "device": [["default", "cpu"], {}]}, "optional": {}},
        "input_order": {"required": ["clip_name", "type", "device"], "optional": []},
    },
    # Samplers
    "KSampler": {
        "input": {
            "required": {
                "model": ["MODEL"], "positive": ["CONDITIONING"], "negative": ["CONDITIONING"], "latent_image": ["LATENT"],
                "seed": ["INT", {"default": 0}], "steps": ["INT", {"default": 20}], "cfg": ["FLOAT", {"default": 8.0}],
                "sampler_name": [["euler", "euler_ancestral", "dpm_2"], {}], "scheduler": [["normal", "karras", "simple"], {}],
                "denoise": ["FLOAT", {"default": 1.0}],
            },
            "optional": {},
        },
        "input_order": {"required": ["model", "positive", "negative", "latent_image", "seed", "steps", "cfg", "sampler_name", "scheduler", "denoise"], "optional": []},
    },
    "KSamplerAdvanced": {
        "input": {
            "required": {
                "model": ["MODEL"], "positive": ["CONDITIONING"], "negative": ["CONDITIONING"], "latent_image": ["LATENT"],
                "add_noise": [["enable", "disable"], {}], "noise_seed": ["INT", {"default": 0}],
                "steps": ["INT", {"default": 20}], "cfg": ["FLOAT", {"default": 8.0}],
                "sampler_name": [["euler", "euler_ancestral"], {}], "scheduler": [["normal", "simple"], {}],
                "start_at_step": ["INT", {"default": 0}], "end_at_step": ["INT", {"default": 10000}],
                "return_with_leftover_noise": [["disable", "enable"], {}],
            },
            "optional": {},
        },
        "input_order": {
            "required": ["model", "positive", "negative", "latent_image", "add_noise", "noise_seed", "steps", "cfg", "sampler_name", "scheduler", "start_at_step", "end_at_step", "return_with_leftover_noise"],
            "optional": [],
        },
    },
    # Latent generators
    "EmptyLatentImage": {
        "input": {"required": {"width": ["INT", {}], "height": ["INT", {}], "batch_size": ["INT", {}]}, "optional": {}},
        "input_order": {"required": ["width", "height", "batch_size"], "optional": []},
    },
    "EmptySD3LatentImage": {
        "input": {"required": {"width": ["INT", {}], "height": ["INT", {}], "batch_size": ["INT", {}]}, "optional": {}},
        "input_order": {"required": ["width", "height", "batch_size"], "optional": []},
    },
    "EmptyHunyuanLatentVideo": {
        "input": {"required": {"width": ["INT", {}], "height": ["INT", {}], "length": ["INT", {}], "batch_size": ["INT", {}]}, "optional": {}},
        "input_order": {"required": ["width", "height", "length", "batch_size"], "optional": []},
    },
    # Model loaders
    "UNETLoader": {
        "input": {"required": {"unet_name": [["model.safetensors"], {}], "weight_dtype": [["default", "fp8_e4m3fn"], {}]}, "optional": {}},
        "input_order": {"required": ["unet_name", "weight_dtype"], "optional": []},
    },
    "VAELoader": {
        "input": {"required": {"vae_name": [["vae.safetensors"], {}]}, "optional": {}},
        "input_order": {"required": ["vae_name"], "optional": []},
    },
    "CheckpointLoaderSimple": {
        "input": {"required": {"ckpt_name": [["model.safetensors"], {}]}, "optional": {}},
        "input_order": {"required": ["ckpt_name"], "optional": []},
    },
    "LoraLoaderModelOnly": {
        "input": {"required": {"model": ["MODEL"], "lora_name": [["lora.safetensors"], {}], "strength_model": ["FLOAT", {}]}, "optional": {}},
        "input_order": {"required": ["model", "lora_name", "strength_model"], "optional": []},
    },
    "ModelSamplingSD3": {
        "input": {"required": {"model": ["MODEL"], "shift": ["FLOAT", {}]}, "optional": {}},
        "input_order": {"required": ["model", "shift"], "optional": []},
    },
    # Video/Image processing
    "VAEDecode": {
        "input": {"required": {"samples": ["LATENT"], "vae": ["VAE"]}, "optional": {}},
        "input_order": {"required": ["samples", "vae"], "optional": []},
    },
    "VAEEncode": {
        "input": {"required": {"pixels": ["IMAGE"], "vae": ["VAE"]}, "optional": {}},
        "input_order": {"required": ["pixels", "vae"], "optional": []},
    },
    "CreateVideo": {
        "input": {"required": {"images": ["IMAGE"], "fps": ["FLOAT", {"default": 16}]}, "optional": {"audio": ["AUDIO"]}},
        "input_order": {"required": ["images", "fps"], "optional": ["audio"]},
    },
    # Save nodes
    "SaveVideo": {
        "input": {
            "required": {
                "video": ["VIDEO"],
                "filename_prefix": ["STRING", {"default": "video/ComfyUI"}],
                "format": ["COMBO", {"default": "auto", "options": ["auto", "mp4"]}],
                "codec": ["COMBO", {"default": "auto", "options": ["auto", "h264"]}],
            },
            "optional": {},
        },
        "input_order": {"required": ["video", "filename_prefix", "format", "codec"], "optional": []},
    },
    "SaveImage": {
        "input": {"required": {"images": ["IMAGE"], "filename_prefix": ["STRING", {}]}, "optional": {}},
        "input_order": {"required": ["images", "filename_prefix"], "optional": []},
    },
    "SaveAnimatedWEBP": {
        "input": {"required": {"images": ["IMAGE"], "filename_prefix": ["STRING", {}], "fps": ["FLOAT", {}], "lossless": ["BOOLEAN", {}], "quality": ["INT", {}], "method": [["default"], {}]}, "optional": {}},
        "input_order": {"required": ["images", "filename_prefix", "fps", "lossless", "quality", "method"], "optional": []},
    },
}


def load_template(template_id: str) -> dict:
    """
    Load workflow template from comfyui-workflow-templates package.

    Args:
        template_id: Template name (e.g., "video_wan2_2_14B_t2v")

    Returns:
        Workflow in graph format (nodes array, links array)

    Requires: pip install comfyui-workflow-templates comfyui-workflow-templates-media-image
    """
    try:
        from comfyui_workflow_templates import get_asset_path
    except ImportError:
        raise ImportError(
            "comfyui-workflow-templates not installed. "
            "Run: pip install comfyui-workflow-templates comfyui-workflow-templates-media-image"
        )

    workflow_path = get_asset_path(template_id, f"{template_id}.json")
    with open(workflow_path) as f:
        return json.load(f)


def _value_matches_type(value, input_spec) -> bool:
    """Check if a widget value matches the expected input type."""
    if input_spec is None:
        return True

    # input_spec is typically [type, config] or just [type]
    if isinstance(input_spec, list) and len(input_spec) > 0:
        type_info = input_spec[0]
        config = input_spec[1] if len(input_spec) > 1 else {}

        # List of allowed values (enum/combo) - older format
        if isinstance(type_info, list):
            # Accept if value is in list, or if value is a string (enum values may differ between versions)
            if value in type_info:
                return True
            # Accept any string for enum - versions may have different allowed values
            if isinstance(value, str) and any(isinstance(v, str) for v in type_info):
                return True
            return False

        # Type string
        if isinstance(type_info, str):
            # COMBO type - options are in config["options"] (newer ComfyUI format)
            if type_info == "COMBO":
                options = config.get("options", []) if isinstance(config, dict) else []
                if value in options:
                    return True
                # Accept any string for combo - versions may have different allowed values
                if isinstance(value, str) and options and any(isinstance(v, str) for v in options):
                    return True
                return False
            elif type_info == "INT":
                return isinstance(value, (int, float)) and not isinstance(value, bool)
            elif type_info == "FLOAT":
                return isinstance(value, (int, float)) and not isinstance(value, bool)
            elif type_info == "STRING":
                return isinstance(value, str)
            elif type_info == "BOOLEAN":
                return isinstance(value, bool)
            # Connection types (MODEL, CLIP, VIDEO, etc.) are handled via links, not widgets
            elif type_info.isupper():
                return False

    return True


def find_nodes(workflow: dict, class_type: str, title_contains: str = None) -> list[tuple[str, dict]]:
    """
    Find nodes in API-format workflow by class_type and optional title pattern.

    Args:
        workflow: Workflow in API format (node IDs as keys)
        class_type: Node class type to match (e.g., "CLIPTextEncode", "KSampler")
        title_contains: Optional substring to match in node title (case-insensitive)

    Returns:
        List of (node_id, node) tuples matching the criteria
    """
    results = []
    for node_id, node in workflow.items():
        if node.get("class_type") == class_type:
            if title_contains is None:
                results.append((node_id, node))
            else:
                title = node.get("_meta", {}).get("title", "")
                if title_contains.lower() in title.lower():
                    results.append((node_id, node))
    return results


def find_node(workflow: dict, class_type: str, title_contains: str = None) -> tuple[str, dict] | tuple[None, None]:
    """Find first node matching class_type and optional title pattern."""
    nodes = find_nodes(workflow, class_type, title_contains)
    return nodes[0] if nodes else (None, None)


def apply_params(workflow: dict, **params) -> dict:
    """
    Apply parameters to workflow nodes by finding them by type/title.

    This works across different workflow types (Qwen, Flux, SDXL, etc.)
    by searching for nodes by their class_type rather than hardcoded IDs.

    Supported params:
        prompt: Text for positive prompt (CLIPTextEncode with "Positive" in title)
        negative: Text for negative prompt (CLIPTextEncode with "Negative" in title)
        width: Image width (EmptySD3LatentImage, EmptyFlux2LatentImage, EmptyLatentImage, or PrimitiveNode)
        height: Image height (same as width)
        seed: Random seed (KSampler, RandomNoise, or SamplerCustom)
        steps: Sampling steps (KSampler or Flux2Scheduler)
        cfg: CFG scale (KSampler or FluxGuidance)
        filename_prefix: Output filename prefix (SaveImage)

    Returns:
        Modified workflow (mutated in place)
    """
    # Helper to find first matching node from a list of types
    def find_first(types: list[str], title: str = None) -> tuple[str, dict] | tuple[None, None]:
        for t in types:
            node_id, node = find_node(workflow, t, title)
            if node:
                return node_id, node
        return None, None

    # CLIP text encode types (standard first, then variants)
    clip_types = ["CLIPTextEncode", "CLIPTextEncodeFlux", "CLIPTextEncodeSD3"]

    # Positive prompt - with "Positive" in title, or first CLIP encoder
    if "prompt" in params:
        node_id, node = find_first(clip_types, "Positive")
        if not node:
            # Fallback: first CLIPTextEncode (many workflows have prompt as first)
            for t in clip_types:
                nodes = find_nodes(workflow, t)
                if nodes:
                    node_id, node = nodes[0]
                    break
        if node:
            node["inputs"]["text"] = params["prompt"]

    # Negative prompt - with "Negative" in title
    if "negative" in params:
        node_id, node = find_first(clip_types, "Negative")
        if node:
            node["inputs"]["text"] = params["negative"]

    # Width/Height - try various latent image/video nodes
    if "width" in params or "height" in params:
        latent_types = [
            # Image
            "EmptySD3LatentImage", "EmptyFlux2LatentImage", "EmptyLatentImage",
            # Video
            "EmptyHunyuanLatentVideo", "EmptyMochiLatentVideo", "EmptyLTXVLatentVideo",
        ]
        node_id, node = find_first(latent_types)
        if node:
            if "width" in params:
                node["inputs"]["width"] = params["width"]
            if "height" in params:
                node["inputs"]["height"] = params["height"]
        else:
            # Try PrimitiveNode with "width"/"height" title (Flux2 style)
            if "width" in params:
                node_id, node = find_node(workflow, "PrimitiveNode", "width")
                if node and "value" in node["inputs"]:
                    node["inputs"]["value"] = params["width"]
            if "height" in params:
                node_id, node = find_node(workflow, "PrimitiveNode", "height")
                if node and "value" in node["inputs"]:
                    node["inputs"]["value"] = params["height"]

    # Sampler types (standard first, then advanced variants)
    sampler_types = ["KSampler", "KSamplerAdvanced", "SamplerCustom", "SamplerCustomAdvanced"]

    # Seed - KSampler variants or RandomNoise
    if "seed" in params:
        node_id, node = find_first(sampler_types)
        if node:
            node["inputs"]["seed"] = params["seed"]
        else:
            node_id, node = find_node(workflow, "RandomNoise")
            if node:
                node["inputs"]["noise_seed"] = params["seed"]

    # Steps - KSampler variants or Flux2Scheduler
    if "steps" in params:
        node_id, node = find_first(sampler_types)
        if node:
            node["inputs"]["steps"] = params["steps"]
        else:
            node_id, node = find_node(workflow, "Flux2Scheduler")
            if node:
                node["inputs"]["steps"] = params["steps"]

    # CFG - KSampler variants or FluxGuidance
    if "cfg" in params:
        node_id, node = find_first(sampler_types)
        if node:
            node["inputs"]["cfg"] = params["cfg"]
        else:
            node_id, node = find_node(workflow, "FluxGuidance")
            if node:
                node["inputs"]["guidance"] = params["cfg"]

    # Filename prefix - SaveImage, SaveVideo, or SaveAnimatedWEBP
    if "filename_prefix" in params:
        save_types = ["SaveImage", "SaveVideo", "SaveAnimatedWEBP", "SaveAnimatedPNG"]
        node_id, node = find_first(save_types)
        if node:
            node["inputs"]["filename_prefix"] = params["filename_prefix"]

    return workflow


def graph_to_api(graph: dict, object_info: dict = None, debug: bool = False) -> dict:
    """
    Convert ComfyUI graph format (from UI) to API format (for /prompt endpoint).

    Args:
        graph: Workflow in graph format (nodes array, links array)
        object_info: Node schemas from /object_info endpoint (uses DEFAULT_OBJECT_INFO if None)
        debug: If True, print debug info about conversion

    Returns:
        Workflow in API format (node IDs as keys)
    """
    if object_info is None:
        object_info = DEFAULT_OBJECT_INFO
    api = {}

    # Build node lookup
    nodes_by_id = {node["id"]: node for node in graph.get("nodes", [])}

    # Build link lookup: link_id -> (from_node_id, from_slot)
    links = {}
    for link in graph.get("links", []):
        # link format: [link_id, from_node, from_slot, to_node, to_slot, type]
        link_id = link[0]
        from_node = link[1]
        from_slot = link[2]
        links[link_id] = (from_node, from_slot)

    def is_skipped_node(node):
        """Check if node should be skipped in API output."""
        if not node:
            return True
        class_type = node.get("type")
        if not class_type or class_type in ("Note", "Reroute", "MarkdownNote"):
            return True
        # mode 2 = muted, mode 4 = bypassed
        if node.get("mode", 0) in (2, 4):
            return True
        return False

    def resolve_link(link_id, visited=None):
        """Follow link through skipped nodes (reroutes, bypassed) to find real source."""
        if visited is None:
            visited = set()
        if link_id in visited:
            return None  # Cycle detection
        visited.add(link_id)

        if link_id not in links:
            return None

        from_node_id, from_slot = links[link_id]
        from_node = nodes_by_id.get(from_node_id)

        if not is_skipped_node(from_node):
            return (from_node_id, from_slot)

        # Node is skipped - follow through its input
        # For bypassed/reroute nodes, output slot 0 passes through input slot 0
        if from_slot == 0 and from_node:
            node_inputs = from_node.get("inputs", [])
            if node_inputs:
                upstream_link = node_inputs[0].get("link")
                if upstream_link is not None:
                    return resolve_link(upstream_link, visited)

        return None

    for node in graph.get("nodes", []):
        node_id = str(node["id"])
        class_type = node.get("type")

        # Skip UI-only nodes (notes, reroutes, etc.)
        if not class_type or class_type in ("Note", "Reroute", "MarkdownNote"):
            continue

        # Skip muted/bypassed nodes (mode 2 = muted, mode 4 = bypassed)
        if node.get("mode", 0) in (2, 4):
            continue

        info = object_info.get(class_type, {})
        inputs = {}

        # Get input specs from schema
        input_specs = {}
        for section in ["required", "optional"]:
            for name, spec in info.get("input", {}).get(section, {}).items():
                input_specs[name] = spec

        # Get input order from schema
        # Note: input_order may be missing in some ComfyUI versions - fall back to input specs keys
        input_order = info.get("input_order", {})
        required_inputs = input_order.get("required", [])
        optional_inputs = input_order.get("optional", [])
        all_input_names = required_inputs + optional_inputs

        # Fallback: if input_order is empty, use keys from input specs
        # This handles older ComfyUI versions that don't provide input_order
        if not all_input_names and input_specs:
            # Use input specs keys, putting required first
            required_spec_keys = list(info.get("input", {}).get("required", {}).keys())
            optional_spec_keys = list(info.get("input", {}).get("optional", {}).keys())
            all_input_names = required_spec_keys + optional_spec_keys

        # Debug: show what we're working with for SaveVideo
        if debug and class_type == "SaveVideo":
            print(f"DEBUG SaveVideo node {node_id}:")
            print(f"  input_order: {input_order}")
            print(f"  all_input_names: {all_input_names}")
            print(f"  input_specs keys: {list(input_specs.keys())}")
            print(f"  widgets_values: {node.get('widgets_values', [])}")

        # Map connections from links (node inputs that are connected)
        connected_inputs = set()
        for inp in node.get("inputs", []):
            link_id = inp.get("link")
            if link_id is not None:
                resolved = resolve_link(link_id)
                if resolved:
                    from_node, from_slot = resolved
                    inputs[inp["name"]] = [str(from_node), from_slot]
                    connected_inputs.add(inp["name"])

        if debug and class_type == "SaveVideo":
            print(f"  connected_inputs: {connected_inputs}")

        # Map widget values to unconnected inputs with type validation
        widgets = node.get("widgets_values", [])
        if isinstance(widgets, dict):
            # Some nodes use dict format for widgets
            for name, value in widgets.items():
                if name not in connected_inputs:
                    inputs[name] = value
        else:
            # List format - map positionally to input names, skipping UI-only widgets
            w_idx = 0
            for name in all_input_names:
                if name in connected_inputs:
                    continue

                # Find next widget value that matches the expected type
                input_spec = input_specs.get(name)
                if debug and class_type == "SaveVideo":
                    print(f"  mapping '{name}': spec={input_spec}, w_idx={w_idx}, widgets[{w_idx}:]={widgets[w_idx:] if w_idx < len(widgets) else '[]'}")
                while w_idx < len(widgets):
                    value = widgets[w_idx]
                    w_idx += 1
                    if _value_matches_type(value, input_spec):
                        inputs[name] = value
                        if debug and class_type == "SaveVideo":
                            print(f"    -> assigned {name}={value}")
                        break
                    # Skip UI-only widgets (e.g., 'randomize', 'fixed', etc.)

        if debug and class_type == "SaveVideo":
            print(f"  final inputs: {inputs}")

        api[node_id] = {
            "class_type": class_type,
            "inputs": inputs,
            "_meta": {"title": node.get("title", class_type)},
        }

    return api


class ComfyUIJob(BaseJob):
    """ComfyUI-specific job with workflow execution helpers"""

    DEFAULT_IMAGE = COMFYUI_IMAGE
    DEFAULT_GPU_TYPE = "l40s"
    HEALTH_ENDPOINT = "/system_stats"

    COMFYUI_PORT = 8188

    def __init__(self, c3: "C3", job, template: str = None, use_lb: bool = False, use_auth: bool = False):
        super().__init__(c3, job)
        self._object_info: dict | None = None
        self._auth_headers: dict | None = None
        self._job_token: str | None = None
        self.template = template  # Template used to launch this job
        self.use_lb = use_lb  # Using HTTPS load balancer
        self.use_auth = use_auth  # Using token auth

    @property
    def base_url(self) -> str:
        """ComfyUI base URL - HTTPS if using lb, HTTP otherwise"""
        if not self._base_url and self.hostname:
            if self.use_lb:
                # HTTPS load balancer - no port needed, uses standard 443
                self._base_url = f"https://{self.hostname}"
            else:
                # Direct HTTP connection to port
                self._base_url = f"http://{self.hostname}:{self.COMFYUI_PORT}"
        return self._base_url or ""

    @property
    def auth_headers(self) -> dict:
        """Headers for authenticated requests to ComfyUI"""
        if self.use_auth:
            # Use job-specific token for LB auth
            if not self._job_token:
                self._job_token = self.c3.jobs.token(self.job_id)
            return {"Authorization": f"Bearer {self._job_token}"}
        else:
            # Use API key for direct connections
            return {"Authorization": f"Bearer {self.c3._api_key}"}

    @classmethod
    def create_for_template(
        cls,
        c3: "C3",
        template: str,
        gpu_type: str = None,
        gpu_count: int = 1,
        runtime: int = 3600,
        lb: int = None,
        auth: bool = False,
        **kwargs,
    ) -> "ComfyUIJob":
        """Create a new ComfyUI job configured for a specific template.

        Args:
            c3: C3 client
            template: Template name (passed as COMFYUI_TEMPLATES env var)
            gpu_type: GPU type
            gpu_count: Number of GPUs
            runtime: Max runtime in seconds
            lb: Port for HTTPS load balancer (e.g., 8188). If set, uses HTTPS.
            auth: Enable Bearer token auth on load balancer
        """
        env = kwargs.pop("env", {}) or {}
        env["COMFYUI_TEMPLATES"] = template

        ports = kwargs.pop("ports", {}) or {}
        if lb:
            # Use HTTPS load balancer
            ports["lb"] = lb
        else:
            # Direct port exposure (HTTP)
            ports[str(cls.COMFYUI_PORT)] = cls.COMFYUI_PORT

        job = c3.jobs.create(
            image=cls.DEFAULT_IMAGE,
            gpu_type=gpu_type or cls.DEFAULT_GPU_TYPE,
            gpu_count=gpu_count,
            runtime=runtime,
            env=env,
            ports=ports,
            auth=auth,
            **kwargs,
        )
        return cls(c3, job, template=template, use_lb=bool(lb), use_auth=auth)

    @classmethod
    def get_instance(
        cls,
        c3: "C3",
        instance: str,
        use_lb: bool = False,
        use_auth: bool = False,
    ) -> "ComfyUIJob":
        """Connect to a specific ComfyUI instance by job ID or hostname.

        Args:
            c3: C3 client
            instance: Job ID (UUID) or hostname
            use_lb: Whether instance uses HTTPS load balancer
            use_auth: Whether instance uses token auth
        """
        # Check if it looks like a UUID (job ID)
        if "-" in instance and len(instance) > 30:
            job = c3.jobs.get(instance)
        else:
            # Assume hostname - search running jobs
            jobs = c3.jobs.list(state="running")
            job = None
            for j in jobs:
                if j.hostname and (j.hostname == instance or j.hostname.startswith(instance)):
                    job = j
                    break
            if not job:
                raise ValueError(f"No running job found with hostname: {instance}")

        return cls(c3, job, use_lb=use_lb, use_auth=use_auth)

    @classmethod
    def get_or_create_for_template(
        cls,
        c3: "C3",
        template: str,
        gpu_type: str = None,
        gpu_count: int = 1,
        runtime: int = 3600,
        reuse: bool = True,
        lb: int = None,
        auth: bool = False,
        **kwargs,
    ) -> "ComfyUIJob":
        """Get existing running job or create new one for a template.

        If reuse=True and a ComfyUI job is already running, it will be reused
        (note: the existing job may have different models loaded).
        """
        if reuse:
            existing = cls.get_running(c3, image_filter=cls.DEFAULT_IMAGE)
            if existing:
                existing.template = template
                # TODO: detect lb/auth from existing job's config
                existing.use_lb = bool(lb)
                existing.use_auth = auth
                return existing

        return cls.create_for_template(
            c3,
            template=template,
            gpu_type=gpu_type,
            gpu_count=gpu_count,
            runtime=runtime,
            lb=lb,
            auth=auth,
            **kwargs,
        )

    def get_object_info(self, refresh: bool = False) -> dict:
        """Fetch node schemas from ComfyUI (cached)"""
        if self._object_info is None or refresh:
            with httpx.Client(timeout=30) as client:
                resp = client.get(
                    f"{self.base_url}/object_info",
                    headers=self.auth_headers,
                )
                resp.raise_for_status()
                self._object_info = resp.json()
        return self._object_info

    def convert_workflow(self, graph: dict, debug: bool = False) -> dict:
        """Convert graph format workflow to API format"""
        object_info = self.get_object_info()
        return graph_to_api(graph, object_info, debug=debug)

    def load_template(self, template_id: str) -> dict:
        """
        Load workflow from comfyui-workflow-templates package.

        Requires: pip install comfyui-workflow-templates comfyui-workflow-templates-media-image
        """
        try:
            from comfyui_workflow_templates import get_asset_path
        except ImportError:
            raise ImportError(
                "comfyui-workflow-templates not installed. "
                "Run: pip install comfyui-workflow-templates comfyui-workflow-templates-media-image"
            )

        workflow_path = get_asset_path(template_id, f"{template_id}.json")
        with open(workflow_path) as f:
            return json.load(f)

    def upload_image(self, file_path: str | Path, filename: str = None) -> str:
        """Upload image to ComfyUI server, returns server filename"""
        file_path = Path(file_path)
        filename = filename or file_path.name

        with httpx.Client(timeout=60) as client:
            with open(file_path, "rb") as f:
                files = {"image": (filename, f, "image/png")}
                resp = client.post(
                    f"{self.base_url}/upload/image",
                    files=files,
                    headers=self.auth_headers,
                )
                resp.raise_for_status()
                return resp.json().get("name", filename)

    def upload_audio(self, file_path: str | Path, filename: str = None) -> str:
        """Upload audio to ComfyUI server, returns server filename"""
        file_path = Path(file_path)
        filename = filename or file_path.name

        with httpx.Client(timeout=60) as client:
            with open(file_path, "rb") as f:
                files = {"audio": (filename, f, "audio/mpeg")}
                resp = client.post(
                    f"{self.base_url}/upload/audio",
                    files=files,
                    headers=self.auth_headers,
                )
                resp.raise_for_status()
                return resp.json().get("name", filename)

    def queue_prompt(self, workflow: dict) -> str:
        """Submit workflow to ComfyUI, returns prompt_id"""
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                f"{self.base_url}/prompt",
                json={"prompt": workflow},
                headers=self.auth_headers,
            )
            if resp.status_code != 200:
                # Include response body in error for debugging
                try:
                    error_detail = resp.json()
                except Exception:
                    error_detail = resp.text
                raise RuntimeError(f"ComfyUI prompt failed ({resp.status_code}): {error_detail}")
            return resp.json()["prompt_id"]

    def get_history(self, prompt_id: str, retries: int = 3) -> dict | None:
        """Get execution history for a prompt"""
        last_error = None
        for attempt in range(retries):
            try:
                with httpx.Client(timeout=30) as client:
                    resp = client.get(
                        f"{self.base_url}/history/{prompt_id}",
                        headers=self.auth_headers,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    return data.get(prompt_id)
            except (httpx.ConnectError, httpx.ReadTimeout) as e:
                last_error = e
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s, 4s
                    continue
                raise

    def wait_for_completion(
        self, prompt_id: str, timeout: float = 300, poll_interval: float = 2
    ) -> dict:
        """Wait for prompt execution to complete, returns history entry"""
        start = time.time()
        consecutive_errors = 0
        max_consecutive_errors = 5

        while time.time() - start < timeout:
            try:
                history = self.get_history(prompt_id)
                consecutive_errors = 0  # Reset on success
                if history:
                    status = history.get("status", {})
                    if status.get("completed"):
                        return history
                    if status.get("status_str") == "error":
                        raise RuntimeError(f"Workflow execution failed: {status}")
            except (httpx.ConnectError, httpx.ReadTimeout) as e:
                consecutive_errors += 1
                if consecutive_errors >= max_consecutive_errors:
                    raise RuntimeError(
                        f"Lost connection to ComfyUI after {consecutive_errors} retries: {e}"
                    )
                # Wait longer on connection errors
                time.sleep(poll_interval * 2)
                continue

            time.sleep(poll_interval)
        raise TimeoutError(f"Workflow did not complete within {timeout}s")

    def download_output(
        self, filename: str, output_dir: str | Path = ".", subfolder: str = "", retries: int = 3
    ) -> Path:
        """Download output file from ComfyUI server.

        If the file already exists, increments the name (file_1.png, file_2.png, etc.)
        """
        output_dir = Path(output_dir)
        if not output_dir.exists():
            output_dir.mkdir(parents=True, exist_ok=True)

        url = f"{self.base_url}/view"
        params = {"filename": filename, "type": "output"}
        if subfolder:
            params["subfolder"] = subfolder

        for attempt in range(retries):
            try:
                with httpx.Client(timeout=120) as client:
                    resp = client.get(url, params=params, headers=self.auth_headers)
                    resp.raise_for_status()

                    # Auto-increment filename if exists
                    output_path = output_dir / filename
                    if output_path.exists():
                        stem = output_path.stem
                        suffix = output_path.suffix
                        i = 1
                        while output_path.exists():
                            output_path = output_dir / f"{stem}_{i}{suffix}"
                            i += 1

                    with open(output_path, "wb") as f:
                        f.write(resp.content)
                    return output_path
            except (httpx.ConnectError, httpx.ReadTimeout) as e:
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise

    def run(
        self,
        workflow: dict,
        timeout: float = 300,
        convert: bool = True,
    ) -> dict:
        """
        Run a workflow and wait for completion.

        Args:
            workflow: Workflow dict (graph or API format)
            timeout: Max seconds to wait for completion
            convert: If True, convert graph format to API format

        Returns:
            History entry with outputs
        """
        # Detect format and convert if needed
        if convert and "nodes" in workflow:
            workflow = self.convert_workflow(workflow)

        prompt_id = self.queue_prompt(workflow)
        return self.wait_for_completion(prompt_id, timeout=timeout)

    def run_template(
        self,
        template_id: str,
        timeout: float = 300,
        **params,
    ) -> dict:
        """
        Run a template from comfyui-workflow-templates with parameter overrides.

        Args:
            template_id: Template name (e.g., "image_qwen_image")
            timeout: Max seconds to wait
            **params: Parameters to override (prompt, negative, width, height, seed, etc.)
                See apply_params() for full list of supported parameters.

        Returns:
            History entry with outputs
        """
        graph = self.load_template(template_id)
        workflow = self.convert_workflow(graph)

        # Apply parameter overrides using type-based node lookup
        apply_params(workflow, **params)

        return self.run(workflow, timeout=timeout, convert=False)

    def get_output_images(self, history: dict) -> list[dict]:
        """Extract output image info from history entry"""
        images = []
        for node_id, node_output in history.get("outputs", {}).items():
            if "images" in node_output:
                for img in node_output["images"]:
                    images.append(img)
        return images
