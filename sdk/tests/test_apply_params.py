"""Tests for apply_params workflow parameter injection.

These tests verify that apply_params correctly finds and modifies nodes
across different workflow types (Qwen, Flux, SDXL, Wan, Hunyuan, etc.)

Run spot check: python tests/test_apply_params.py
Run with pytest: pytest tests/test_apply_params.py -v
"""
import json
import sys
from pathlib import Path

# pytest is optional for spot check mode
try:
    import pytest
    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False
    # Stub for running without pytest
    class pytest:
        @staticmethod
        def fixture(fn): return fn
        @staticmethod
        def skip(msg): raise Exception(f"SKIP: {msg}")
        class mark:
            @staticmethod
            def parametrize(*args, **kwargs):
                def decorator(fn): return fn
                return decorator

sys.path.insert(0, str(Path(__file__).parent.parent))
from c3.job.comfyui import apply_params, find_node, find_nodes, graph_to_api


# Minimal mock object_info for graph_to_api conversion
MOCK_OBJECT_INFO = {
    # Text encoders
    "CLIPTextEncode": {"input": {"required": {"text": ["STRING", {}]}, "optional": {}}, "input_order": {"required": ["text"], "optional": []}},
    "CLIPTextEncodeFlux": {"input": {"required": {"text": ["STRING", {}], "guidance": ["FLOAT", {}]}, "optional": {}}, "input_order": {"required": ["text", "guidance"], "optional": []}},
    "CLIPTextEncodeSD3": {"input": {"required": {"text": ["STRING", {}]}, "optional": {}}, "input_order": {"required": ["text"], "optional": []}},
    # Samplers
    "KSampler": {"input": {"required": {"seed": ["INT", {}], "steps": ["INT", {}], "cfg": ["FLOAT", {}], "sampler_name": [["euler"], {}], "scheduler": [["normal"], {}], "denoise": ["FLOAT", {}]}, "optional": {}}, "input_order": {"required": ["seed", "steps", "cfg", "sampler_name", "scheduler", "denoise"], "optional": []}},
    "KSamplerAdvanced": {"input": {"required": {"seed": ["INT", {}], "steps": ["INT", {}], "cfg": ["FLOAT", {}], "sampler_name": [["euler"], {}], "scheduler": [["normal"], {}], "start_at_step": ["INT", {}], "end_at_step": ["INT", {}], "return_with_leftover_noise": [["disable"], {}]}, "optional": {}}, "input_order": {"required": ["seed", "steps", "cfg", "sampler_name", "scheduler", "start_at_step", "end_at_step", "return_with_leftover_noise"], "optional": []}},
    "RandomNoise": {"input": {"required": {"noise_seed": ["INT", {}]}, "optional": {}}, "input_order": {"required": ["noise_seed"], "optional": []}},
    # Latent (image)
    "EmptyLatentImage": {"input": {"required": {"width": ["INT", {}], "height": ["INT", {}], "batch_size": ["INT", {}]}, "optional": {}}, "input_order": {"required": ["width", "height", "batch_size"], "optional": []}},
    "EmptySD3LatentImage": {"input": {"required": {"width": ["INT", {}], "height": ["INT", {}], "batch_size": ["INT", {}]}, "optional": {}}, "input_order": {"required": ["width", "height", "batch_size"], "optional": []}},
    # Latent (video)
    "EmptyHunyuanLatentVideo": {"input": {"required": {"width": ["INT", {}], "height": ["INT", {}], "length": ["INT", {}], "batch_size": ["INT", {}]}, "optional": {}}, "input_order": {"required": ["width", "height", "length", "batch_size"], "optional": []}},
    "EmptyMochiLatentVideo": {"input": {"required": {"width": ["INT", {}], "height": ["INT", {}], "length": ["INT", {}], "batch_size": ["INT", {}]}, "optional": {}}, "input_order": {"required": ["width", "height", "length", "batch_size"], "optional": []}},
    "EmptyLTXVLatentVideo": {"input": {"required": {"width": ["INT", {}], "height": ["INT", {}], "length": ["INT", {}], "batch_size": ["INT", {}]}, "optional": {}}, "input_order": {"required": ["width", "height", "length", "batch_size"], "optional": []}},
    # Save
    "SaveImage": {"input": {"required": {"filename_prefix": ["STRING", {}]}, "optional": {}}, "input_order": {"required": ["filename_prefix"], "optional": []}},
    # CRITICAL: SaveVideo has codec and format as required inputs (was missing, caused bug!)
    "SaveVideo": {"input": {"required": {"filename_prefix": ["STRING", {}], "codec": [["auto", "h264", "h265", "vp9"], {}], "format": [["auto", "mp4", "webm"], {}]}, "optional": {}}, "input_order": {"required": ["filename_prefix", "codec", "format"], "optional": []}},
    "SaveAnimatedWEBP": {"input": {"required": {"filename_prefix": ["STRING", {}], "fps": ["FLOAT", {}], "lossless": ["BOOLEAN", {}], "quality": ["INT", {}], "method": [["default"], {}]}, "optional": {}}, "input_order": {"required": ["filename_prefix", "fps", "lossless", "quality", "method"], "optional": []}},
    "SaveAnimatedPNG": {"input": {"required": {"filename_prefix": ["STRING", {}], "fps": ["FLOAT", {}], "compress_level": ["INT", {}]}, "optional": {}}, "input_order": {"required": ["filename_prefix", "fps", "compress_level"], "optional": []}},
    # Schedulers
    "Flux2Scheduler": {"input": {"required": {"steps": ["INT", {}], "width": ["INT", {}], "height": ["INT", {}]}, "optional": {}}, "input_order": {"required": ["steps", "width", "height"], "optional": []}},
    "FluxGuidance": {"input": {"required": {"guidance": ["FLOAT", {}]}, "optional": {}}, "input_order": {"required": ["guidance"], "optional": []}},
}


def get_template_path(template_id: str) -> Path:
    """Find template JSON in extracted packages."""
    for bundle_dir in Path("/tmp/comfyui-pkg").glob("extracted*/*/templates"):
        template_path = bundle_dir / f"{template_id}.json"
        if template_path.exists():
            return template_path
    raise FileNotFoundError(f"Template {template_id} not found")


def load_and_convert(template_id: str) -> dict:
    """Load template and convert to API format."""
    path = get_template_path(template_id)
    with open(path) as f:
        graph = json.load(f)
    return graph_to_api(graph, MOCK_OBJECT_INFO)


def check_params_applied(workflow: dict) -> dict:
    """Apply test params and return what was applied."""
    apply_params(
        workflow,
        prompt="TEST_PROMPT",
        negative="TEST_NEGATIVE",
        seed=99999,
        steps=42,
        cfg=6.66,
        width=1280,
        height=720,
        filename_prefix="TEST_PREFIX",
    )

    applied = {}
    for node_id, node in workflow.items():
        for k, v in node.get("inputs", {}).items():
            if v == "TEST_PROMPT":
                applied["prompt"] = f"{node_id}.{k}"
            elif v == "TEST_NEGATIVE":
                applied["negative"] = f"{node_id}.{k}"
            elif v == 99999:
                applied["seed"] = f"{node_id}.{k}"
            elif v == 42:
                applied["steps"] = f"{node_id}.{k}"
            elif v == 6.66:
                applied["cfg"] = f"{node_id}.{k}"
            elif v == 1280:
                applied["width"] = f"{node_id}.{k}"
            elif v == 720:
                applied["height"] = f"{node_id}.{k}"
            elif v == "TEST_PREFIX":
                applied["filename_prefix"] = f"{node_id}.{k}"
    return applied


class TestFindNode:
    """Tests for find_node/find_nodes helpers."""

    def test_find_by_class_type(self):
        workflow = {
            "1": {"class_type": "CLIPTextEncode", "inputs": {}, "_meta": {"title": "Positive"}},
            "2": {"class_type": "KSampler", "inputs": {}, "_meta": {"title": "Sampler"}},
        }
        node_id, node = find_node(workflow, "CLIPTextEncode")
        assert node_id == "1"

    def test_find_by_title(self):
        workflow = {
            "1": {"class_type": "CLIPTextEncode", "inputs": {}, "_meta": {"title": "CLIP Text Encode (Positive Prompt)"}},
            "2": {"class_type": "CLIPTextEncode", "inputs": {}, "_meta": {"title": "CLIP Text Encode (Negative Prompt)"}},
        }
        node_id, node = find_node(workflow, "CLIPTextEncode", "Negative")
        assert node_id == "2"

    def test_find_not_found(self):
        workflow = {"1": {"class_type": "KSampler", "inputs": {}, "_meta": {}}}
        node_id, node = find_node(workflow, "CLIPTextEncode")
        assert node_id is None


class TestApplyParamsUnit:
    """Unit tests for apply_params with mock workflows."""

    def test_ksampler_params(self):
        workflow = {
            "3": {"class_type": "KSampler", "inputs": {"seed": 0, "steps": 20, "cfg": 7.0}, "_meta": {}},
        }
        apply_params(workflow, seed=12345, steps=30, cfg=5.0)
        assert workflow["3"]["inputs"]["seed"] == 12345
        assert workflow["3"]["inputs"]["steps"] == 30
        assert workflow["3"]["inputs"]["cfg"] == 5.0

    def test_ksampler_advanced_params(self):
        workflow = {
            "10": {"class_type": "KSamplerAdvanced", "inputs": {"seed": 0, "steps": 20, "cfg": 7.0}, "_meta": {}},
        }
        apply_params(workflow, seed=12345, steps=30, cfg=5.0)
        assert workflow["10"]["inputs"]["seed"] == 12345
        assert workflow["10"]["inputs"]["steps"] == 30
        assert workflow["10"]["inputs"]["cfg"] == 5.0

    def test_random_noise_seed(self):
        workflow = {
            "25": {"class_type": "RandomNoise", "inputs": {"noise_seed": 0}, "_meta": {}},
        }
        apply_params(workflow, seed=99999)
        assert workflow["25"]["inputs"]["noise_seed"] == 99999

    def test_save_video(self):
        workflow = {
            "60": {"class_type": "SaveVideo", "inputs": {"filename_prefix": "old"}, "_meta": {}},
        }
        apply_params(workflow, filename_prefix="new_video")
        assert workflow["60"]["inputs"]["filename_prefix"] == "new_video"


# Text-to-Image templates
TEXT_TO_IMAGE_TEMPLATES = [
    "image_qwen_image",
    "flux_dev_full_text_to_image",
    "flux_schnell",
    "sdxl_simple_example",
    "image_chroma_text_to_image",
]

# Text-to-Video templates
TEXT_TO_VIDEO_TEMPLATES = [
    "video_hunyuan_video_1.5_720p_t2v",
    "video_wan2.1_alpha_t2v_14B",
    "video_wan2_2_14B_t2v",
    "hunyuan_video_text_to_video",
]


@pytest.fixture
def skip_if_no_templates():
    """Skip test if templates not available."""
    try:
        get_template_path("image_qwen_image")
    except FileNotFoundError:
        pytest.skip("Templates not installed - run from /tmp/comfyui-pkg")


class TestTextToImage:
    """Test apply_params on text-to-image templates."""

    @pytest.mark.parametrize("template_id", TEXT_TO_IMAGE_TEMPLATES)
    def test_text_to_image(self, skip_if_no_templates, template_id):
        """Verify all expected params are applied to text-to-image workflows."""
        try:
            workflow = load_and_convert(template_id)
        except FileNotFoundError:
            pytest.skip(f"Template {template_id} not found")

        applied = check_params_applied(workflow)

        # Required params for t2i
        assert "prompt" in applied, f"{template_id}: prompt not applied"
        assert "seed" in applied, f"{template_id}: seed not applied"
        assert "steps" in applied, f"{template_id}: steps not applied"
        assert "cfg" in applied, f"{template_id}: cfg not applied"
        assert "width" in applied, f"{template_id}: width not applied"
        assert "height" in applied, f"{template_id}: height not applied"
        assert "filename_prefix" in applied, f"{template_id}: filename_prefix not applied"

        print(f"\n{template_id}: {applied}")


class TestTextToVideo:
    """Test apply_params on text-to-video templates."""

    @pytest.mark.parametrize("template_id", TEXT_TO_VIDEO_TEMPLATES)
    def test_text_to_video(self, skip_if_no_templates, template_id):
        """Verify all expected params are applied to text-to-video workflows."""
        try:
            workflow = load_and_convert(template_id)
        except FileNotFoundError:
            pytest.skip(f"Template {template_id} not found")

        applied = check_params_applied(workflow)

        # Required params for t2v
        assert "prompt" in applied, f"{template_id}: prompt not applied"
        assert "seed" in applied, f"{template_id}: seed not applied"
        assert "steps" in applied, f"{template_id}: steps not applied"
        assert "cfg" in applied, f"{template_id}: cfg not applied"
        # width/height may not be in all video templates
        assert "filename_prefix" in applied, f"{template_id}: filename_prefix not applied"

        print(f"\n{template_id}: {applied}")


if __name__ == "__main__":
    # Quick spot check without pytest
    print("=" * 60)
    print("Text-to-Image Templates")
    print("=" * 60)
    for t in TEXT_TO_IMAGE_TEMPLATES:
        try:
            workflow = load_and_convert(t)
            applied = check_params_applied(workflow)
            missing = {"prompt", "seed", "steps", "cfg", "width", "height", "filename_prefix"} - set(applied.keys())
            status = "OK" if not missing else f"MISSING: {missing}"
            print(f"{t}: {status}")
            if missing:
                print(f"  Applied: {applied}")
        except FileNotFoundError:
            print(f"{t}: SKIPPED (not found)")
        except Exception as e:
            print(f"{t}: ERROR - {e}")

    print("\n" + "=" * 60)
    print("Text-to-Video Templates")
    print("=" * 60)
    for t in TEXT_TO_VIDEO_TEMPLATES:
        try:
            workflow = load_and_convert(t)
            applied = check_params_applied(workflow)
            missing = {"prompt", "seed", "steps", "cfg", "filename_prefix"} - set(applied.keys())
            status = "OK" if not missing else f"MISSING: {missing}"
            print(f"{t}: {status}")
            if missing:
                print(f"  Applied: {applied}")
        except FileNotFoundError:
            print(f"{t}: SKIPPED (not found)")
        except Exception as e:
            print(f"{t}: ERROR - {e}")
