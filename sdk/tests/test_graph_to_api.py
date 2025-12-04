"""Tests for graph_to_api workflow conversion.

These tests verify that graph_to_api correctly converts ComfyUI graph format
(from the UI) to API format (for /prompt endpoint), including proper widget
value mapping for all node types.

The bug this catches: SaveVideo node has widgets_values ["video/ComfyUI", "auto", "auto"]
which should map to filename_prefix, codec, format. If the object_info doesn't include
codec and format in input_order, those values get silently dropped and the workflow
fails with "Required input is missing: codec/format".

Run: pytest tests/test_graph_to_api.py -v
"""
import json
import sys
from pathlib import Path

try:
    import pytest
    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False
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
from c3.job.comfyui import graph_to_api, _value_matches_type


# Real object_info structure matching current ComfyUI server
# This must stay in sync with actual ComfyUI node definitions!
OBJECT_INFO = {
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
                "model": ["MODEL"],
                "positive": ["CONDITIONING"],
                "negative": ["CONDITIONING"],
                "latent_image": ["LATENT"],
                "seed": ["INT", {"default": 0}],
                "steps": ["INT", {"default": 20}],
                "cfg": ["FLOAT", {"default": 8.0}],
                "sampler_name": [["euler", "euler_ancestral", "dpm_2"], {}],
                "scheduler": [["normal", "karras", "simple"], {}],
                "denoise": ["FLOAT", {"default": 1.0}],
            },
            "optional": {},
        },
        "input_order": {"required": ["model", "positive", "negative", "latent_image", "seed", "steps", "cfg", "sampler_name", "scheduler", "denoise"], "optional": []},
    },
    "KSamplerAdvanced": {
        "input": {
            "required": {
                "model": ["MODEL"],
                "positive": ["CONDITIONING"],
                "negative": ["CONDITIONING"],
                "latent_image": ["LATENT"],
                "add_noise": [["enable", "disable"], {}],
                "seed": ["INT", {"default": 0}],
                "control_after_generate": [["fixed", "increment", "decrement", "randomize"], {}],
                "steps": ["INT", {"default": 20}],
                "cfg": ["FLOAT", {"default": 8.0}],
                "sampler_name": [["euler", "euler_ancestral"], {}],
                "scheduler": [["normal", "simple"], {}],
                "start_at_step": ["INT", {"default": 0}],
                "end_at_step": ["INT", {"default": 10000}],
                "return_with_leftover_noise": [["disable", "enable"], {}],
            },
            "optional": {},
        },
        "input_order": {
            "required": ["model", "positive", "negative", "latent_image", "add_noise", "seed", "control_after_generate", "steps", "cfg", "sampler_name", "scheduler", "start_at_step", "end_at_step", "return_with_leftover_noise"],
            "optional": [],
        },
    },
    # Latent video
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
    "LoraLoaderModelOnly": {
        "input": {"required": {"model": ["MODEL"], "lora_name": [["lora.safetensors"], {}], "strength_model": ["FLOAT", {}]}, "optional": {}},
        "input_order": {"required": ["model", "lora_name", "strength_model"], "optional": []},
    },
    "ModelSamplingSD3": {
        "input": {"required": {"model": ["MODEL"], "shift": ["FLOAT", {}]}, "optional": {}},
        "input_order": {"required": ["model", "shift"], "optional": []},
    },
    # Video nodes
    "VAEDecode": {
        "input": {"required": {"samples": ["LATENT"], "vae": ["VAE"]}, "optional": {}},
        "input_order": {"required": ["samples", "vae"], "optional": []},
    },
    "CreateVideo": {
        "input": {"required": {"images": ["IMAGE"], "frame_rate": ["FLOAT", {"default": 16}]}, "optional": {"audio": ["AUDIO"]}},
        "input_order": {"required": ["images", "frame_rate"], "optional": ["audio"]},
    },
    # CRITICAL: SaveVideo must include codec and format!
    # Uses COMBO type (newer ComfyUI format) - options are in config["options"]
    "SaveVideo": {
        "input": {
            "required": {
                "video": ["VIDEO", {"tooltip": "The video to save."}],
                "filename_prefix": ["STRING", {"default": "video/ComfyUI"}],
                "format": ["COMBO", {"default": "auto", "options": ["auto", "mp4"]}],
                "codec": ["COMBO", {"default": "auto", "options": ["auto", "h264"]}],
            },
            "optional": {},
        },
        "input_order": {"required": ["video", "filename_prefix", "format", "codec"], "optional": []},
    },
    # Image save
    "SaveImage": {
        "input": {"required": {"images": ["IMAGE"], "filename_prefix": ["STRING", {}]}, "optional": {}},
        "input_order": {"required": ["images", "filename_prefix"], "optional": []},
    },
}


def get_template_path(template_id: str) -> Path:
    """Find template JSON in extracted packages."""
    for bundle_dir in Path("/tmp/comfyui-pkg").glob("extracted*/*/templates"):
        template_path = bundle_dir / f"{template_id}.json"
        if template_path.exists():
            return template_path
    raise FileNotFoundError(f"Template {template_id} not found")


class TestValueMatchesType:
    """Tests for _value_matches_type helper."""

    def test_string_type(self):
        assert _value_matches_type("hello", ["STRING", {}]) is True
        assert _value_matches_type(123, ["STRING", {}]) is False

    def test_int_type(self):
        assert _value_matches_type(42, ["INT", {}]) is True
        assert _value_matches_type(3.14, ["INT", {}]) is True  # floats accepted
        assert _value_matches_type("42", ["INT", {}]) is False

    def test_float_type(self):
        assert _value_matches_type(3.14, ["FLOAT", {}]) is True
        assert _value_matches_type(42, ["FLOAT", {}]) is True  # ints accepted
        assert _value_matches_type("3.14", ["FLOAT", {}]) is False

    def test_boolean_type(self):
        assert _value_matches_type(True, ["BOOLEAN", {}]) is True
        assert _value_matches_type(False, ["BOOLEAN", {}]) is True
        assert _value_matches_type(1, ["BOOLEAN", {}]) is False

    def test_enum_type_exact_match(self):
        """Value in allowed list should match."""
        assert _value_matches_type("h264", [["h264", "h265", "vp9"], {}]) is True
        assert _value_matches_type("auto", [["auto", "h264"], {}]) is True

    def test_enum_type_string_fallback(self):
        """Any string should match enum if enum has string values (version compat)."""
        # "auto" not in list but should still match since it's a string enum
        assert _value_matches_type("auto", [["h264", "h265"], {}]) is True
        assert _value_matches_type("unknown_codec", [["h264", "h265"], {}]) is True

    def test_combo_type_exact_match(self):
        """COMBO type with options in config (newer ComfyUI format)."""
        # This is how newer ComfyUI returns enum specs
        spec = ["COMBO", {"options": ["auto", "h264", "h265"]}]
        assert _value_matches_type("auto", spec) is True
        assert _value_matches_type("h264", spec) is True

    def test_combo_type_string_fallback(self):
        """COMBO type should accept any string (version compat)."""
        spec = ["COMBO", {"options": ["h264", "h265"]}]
        # "auto" not in options but should match since it's a string combo
        assert _value_matches_type("auto", spec) is True
        assert _value_matches_type("unknown", spec) is True

    def test_combo_type_rejects_non_string(self):
        """COMBO type should reject non-string values."""
        spec = ["COMBO", {"options": ["auto", "h264"]}]
        assert _value_matches_type(123, spec) is False
        assert _value_matches_type(True, spec) is False

    def test_connection_type_rejected(self):
        """Connection types (uppercase) should be rejected as widget values."""
        assert _value_matches_type("anything", ["MODEL", {}]) is False
        assert _value_matches_type("anything", ["VIDEO", {}]) is False
        assert _value_matches_type("anything", ["LATENT", {}]) is False

    def test_none_spec_accepts_all(self):
        """None input_spec should accept any value."""
        assert _value_matches_type("anything", None) is True
        assert _value_matches_type(123, None) is True


class TestGraphToApiBasic:
    """Basic tests for graph_to_api conversion."""

    def test_simple_node_conversion(self):
        """Single node with widgets should convert correctly."""
        # Note: SaveImage needs a connected images input, otherwise the widget
        # mapping fails because it tries to find widgets for the "images" connection type
        graph = {
            "nodes": [
                {
                    "id": 2,
                    "type": "VAEDecode",  # Source node providing IMAGE
                    "mode": 0,
                    "inputs": [],
                    "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [1]}],
                    "widgets_values": [],
                },
                {
                    "id": 1,
                    "type": "SaveImage",
                    "mode": 0,
                    "inputs": [{"name": "images", "link": 1}],
                    "widgets_values": ["output/test"],
                }
            ],
            "links": [[1, 2, 0, 1, 0, "IMAGE"]],
        }
        api = graph_to_api(graph, OBJECT_INFO)
        assert "1" in api
        assert api["1"]["class_type"] == "SaveImage"
        assert api["1"]["inputs"]["filename_prefix"] == "output/test"

    def test_skips_note_nodes(self):
        """Note and MarkdownNote nodes should be skipped."""
        graph = {
            "nodes": [
                {"id": 1, "type": "Note", "mode": 0, "widgets_values": ["some note"]},
                {"id": 2, "type": "MarkdownNote", "mode": 0, "widgets_values": ["# Title"]},
                {"id": 3, "type": "SaveImage", "mode": 0, "inputs": [], "widgets_values": ["test"]},
            ],
            "links": [],
        }
        api = graph_to_api(graph, OBJECT_INFO)
        assert "1" not in api  # Note skipped
        assert "2" not in api  # MarkdownNote skipped
        assert "3" in api  # SaveImage included

    def test_skips_muted_nodes(self):
        """Muted nodes (mode=2) should be skipped."""
        graph = {
            "nodes": [
                {"id": 1, "type": "SaveImage", "mode": 2, "inputs": [], "widgets_values": ["muted"]},
                {"id": 2, "type": "SaveImage", "mode": 0, "inputs": [], "widgets_values": ["active"]},
            ],
            "links": [],
        }
        api = graph_to_api(graph, OBJECT_INFO)
        assert "1" not in api  # muted
        assert "2" in api

    def test_skips_bypassed_nodes(self):
        """Bypassed nodes (mode=4) should be skipped."""
        graph = {
            "nodes": [
                {"id": 1, "type": "SaveImage", "mode": 4, "inputs": [], "widgets_values": ["bypassed"]},
                {"id": 2, "type": "SaveImage", "mode": 0, "inputs": [], "widgets_values": ["active"]},
            ],
            "links": [],
        }
        api = graph_to_api(graph, OBJECT_INFO)
        assert "1" not in api  # bypassed
        assert "2" in api


class TestSaveVideoConversion:
    """Tests specifically for SaveVideo node conversion - the bug we're catching."""

    def test_save_video_has_codec_and_format(self):
        """SaveVideo must have codec and format after conversion.

        This is the critical test! The bug was that codec and format were
        silently dropped because COMBO type wasn't handled properly.
        """
        # Note: input_order is [video, filename_prefix, format, codec]
        # widgets_values are positional: filename_prefix, format, codec
        graph = {
            "nodes": [
                # Source node that provides VIDEO
                {
                    "id": 88,
                    "type": "CreateVideo",
                    "mode": 0,
                    "inputs": [{"name": "images", "link": None}],
                    "outputs": [{"name": "VIDEO", "type": "VIDEO", "links": [147]}],
                    "widgets_values": [16],
                },
                # SaveVideo node that receives VIDEO
                {
                    "id": 80,
                    "type": "SaveVideo",
                    "mode": 0,
                    "inputs": [{"name": "video", "link": 147}],
                    "widgets_values": ["video/ComfyUI", "auto", "auto"],  # filename_prefix, format, codec
                }
            ],
            "links": [[147, 88, 0, 80, 0, "VIDEO"]],
        }
        api = graph_to_api(graph, OBJECT_INFO)

        assert "80" in api
        assert api["80"]["class_type"] == "SaveVideo"
        inputs = api["80"]["inputs"]

        # CRITICAL: These must all be present!
        assert "filename_prefix" in inputs, "filename_prefix missing from SaveVideo"
        assert "format" in inputs, "format missing from SaveVideo - THIS IS THE BUG"
        assert "codec" in inputs, "codec missing from SaveVideo - THIS IS THE BUG"

        assert inputs["filename_prefix"] == "video/ComfyUI"
        assert inputs["format"] == "auto"
        assert inputs["codec"] == "auto"

    def test_save_video_with_custom_values(self):
        """SaveVideo with non-default codec/format."""
        # Note: input_order is [video, filename_prefix, format, codec]
        # So widgets_values order is: filename_prefix, format, codec
        graph = {
            "nodes": [
                # Source node
                {
                    "id": 2,
                    "type": "CreateVideo",
                    "mode": 0,
                    "inputs": [],
                    "outputs": [{"name": "VIDEO", "type": "VIDEO", "links": [1]}],
                    "widgets_values": [24],
                },
                # SaveVideo
                {
                    "id": 1,
                    "type": "SaveVideo",
                    "mode": 0,
                    "inputs": [{"name": "video", "link": 1}],
                    "widgets_values": ["my_video", "mp4", "h264"],  # filename_prefix, format, codec
                }
            ],
            "links": [[1, 2, 0, 1, 0, "VIDEO"]],
        }
        api = graph_to_api(graph, OBJECT_INFO)

        inputs = api["1"]["inputs"]
        assert inputs["filename_prefix"] == "my_video"
        assert inputs["format"] == "mp4"
        assert inputs["codec"] == "h264"


class TestKSamplerAdvancedConversion:
    """Tests for KSamplerAdvanced which has many widgets."""

    def test_ksampler_advanced_all_widgets(self):
        """KSamplerAdvanced has 10 widget values that must map correctly."""
        graph = {
            "nodes": [
                # Source nodes for connections
                {"id": 82, "type": "UNETLoader", "mode": 0, "inputs": [], "outputs": [{"name": "MODEL", "type": "MODEL", "links": [181]}], "widgets_values": ["model.safetensors", "default"]},
                {"id": 89, "type": "CLIPTextEncode", "mode": 0, "inputs": [], "outputs": [{"name": "CONDITIONING", "type": "CONDITIONING", "links": [149]}], "widgets_values": ["positive"]},
                {"id": 72, "type": "CLIPTextEncode", "mode": 0, "inputs": [], "outputs": [{"name": "CONDITIONING", "type": "CONDITIONING", "links": [150]}], "widgets_values": ["negative"]},
                {"id": 74, "type": "EmptyHunyuanLatentVideo", "mode": 0, "inputs": [], "outputs": [{"name": "LATENT", "type": "LATENT", "links": [151]}], "widgets_values": [640, 640, 81, 1]},
                # KSamplerAdvanced
                {
                    "id": 81,
                    "type": "KSamplerAdvanced",
                    "mode": 0,
                    "inputs": [
                        {"name": "model", "link": 181},
                        {"name": "positive", "link": 149},
                        {"name": "negative", "link": 150},
                        {"name": "latent_image", "link": 151},
                    ],
                    "widgets_values": [
                        "enable",      # add_noise
                        392459563371087,  # seed
                        "randomize",   # control_after_generate
                        4,             # steps
                        1,             # cfg
                        "euler",       # sampler_name
                        "simple",      # scheduler
                        0,             # start_at_step
                        2,             # end_at_step
                        "enable",      # return_with_leftover_noise
                    ],
                }
            ],
            "links": [
                [181, 82, 0, 81, 0, "MODEL"],
                [149, 89, 0, 81, 1, "CONDITIONING"],
                [150, 72, 0, 81, 2, "CONDITIONING"],
                [151, 74, 0, 81, 3, "LATENT"],
            ],
        }
        api = graph_to_api(graph, OBJECT_INFO)

        inputs = api["81"]["inputs"]
        assert inputs["add_noise"] == "enable"
        assert inputs["seed"] == 392459563371087
        assert inputs["control_after_generate"] == "randomize"
        assert inputs["steps"] == 4
        assert inputs["cfg"] == 1
        assert inputs["sampler_name"] == "euler"
        assert inputs["scheduler"] == "simple"
        assert inputs["start_at_step"] == 0
        assert inputs["end_at_step"] == 2
        assert inputs["return_with_leftover_noise"] == "enable"


class TestMissingInputOrder:
    """Tests for handling missing input_order in object_info (older ComfyUI versions)."""

    def test_save_video_without_input_order(self):
        """SaveVideo should work even if server doesn't provide input_order.

        This is the likely root cause of the production bug - older ComfyUI
        versions or certain configurations don't include input_order.
        """
        # Object info WITHOUT input_order - only has input specs
        object_info_no_order = {
            "CreateVideo": {
                "input": {"required": {"images": ["IMAGE"], "frame_rate": ["FLOAT", {}]}, "optional": {"audio": ["AUDIO"]}},
                # No input_order!
            },
            "SaveVideo": {
                "input": {
                    "required": {
                        "video": ["VIDEO"],
                        "filename_prefix": ["STRING", {}],
                        "codec": [["auto", "h264", "h265"], {}],
                        "format": [["auto", "mp4", "webm"], {}],
                    },
                    "optional": {},
                },
                # No input_order! This is what might be happening in production
            },
        }

        graph = {
            "nodes": [
                {
                    "id": 88,
                    "type": "CreateVideo",
                    "mode": 0,
                    "inputs": [],
                    "outputs": [{"name": "VIDEO", "type": "VIDEO", "links": [147]}],
                    "widgets_values": [16],
                },
                {
                    "id": 80,
                    "type": "SaveVideo",
                    "mode": 0,
                    "inputs": [{"name": "video", "link": 147}],
                    "widgets_values": ["video/ComfyUI", "auto", "auto"],
                }
            ],
            "links": [[147, 88, 0, 80, 0, "VIDEO"]],
        }

        api = graph_to_api(graph, object_info_no_order)

        inputs = api["80"]["inputs"]
        # Even without input_order, we should fall back to input spec keys
        assert "filename_prefix" in inputs, "filename_prefix missing when input_order absent"
        assert "codec" in inputs, "codec missing when input_order absent - FALLBACK FAILED"
        assert "format" in inputs, "format missing when input_order absent - FALLBACK FAILED"

        assert inputs["filename_prefix"] == "video/ComfyUI"
        assert inputs["codec"] == "auto"
        assert inputs["format"] == "auto"


class TestRealTemplateConversion:
    """Integration tests using real workflow templates."""

    def test_video_wan2_2_14B_t2v_save_video(self):
        """Test the actual video_wan2_2_14B_t2v template SaveVideo conversion.

        This is the exact scenario that was failing:
        - Template has SaveVideo with widgets_values ["video/ComfyUI", "auto", "auto"]
        - These must map to filename_prefix, codec, format
        - If they don't, ComfyUI returns 400: "Required input is missing: codec"
        """
        try:
            path = get_template_path("video_wan2_2_14B_t2v")
        except FileNotFoundError:
            pytest.skip("Template not found")

        with open(path) as f:
            graph = json.load(f)

        api = graph_to_api(graph, OBJECT_INFO)

        # Find SaveVideo node (id 80 in this template)
        save_video_nodes = [(k, v) for k, v in api.items() if v["class_type"] == "SaveVideo"]
        assert len(save_video_nodes) >= 1, "No SaveVideo node found in converted workflow"

        for node_id, node in save_video_nodes:
            inputs = node["inputs"]
            assert "filename_prefix" in inputs, f"SaveVideo {node_id}: missing filename_prefix"
            assert "codec" in inputs, f"SaveVideo {node_id}: missing codec - THIS IS THE BUG WE'RE CATCHING"
            assert "format" in inputs, f"SaveVideo {node_id}: missing format - THIS IS THE BUG WE'RE CATCHING"

    def test_video_wan2_2_14B_t2v_all_nodes_have_required_inputs(self):
        """All nodes in converted workflow should have their required inputs."""
        try:
            path = get_template_path("video_wan2_2_14B_t2v")
        except FileNotFoundError:
            pytest.skip("Template not found")

        with open(path) as f:
            graph = json.load(f)

        api = graph_to_api(graph, OBJECT_INFO)

        # Check each node has inputs for all required non-connection fields
        for node_id, node in api.items():
            class_type = node["class_type"]
            if class_type not in OBJECT_INFO:
                continue  # Skip unknown node types

            info = OBJECT_INFO[class_type]
            required_inputs = info.get("input_order", {}).get("required", [])
            input_specs = info.get("input", {}).get("required", {})

            for input_name in required_inputs:
                spec = input_specs.get(input_name, [])
                # Skip connection types - they come from links
                if spec and isinstance(spec[0], str) and spec[0].isupper():
                    continue
                # Widget inputs should be present
                assert input_name in node["inputs"], \
                    f"Node {node_id} ({class_type}): missing required input '{input_name}'"


if __name__ == "__main__":
    print("=" * 70)
    print("Testing graph_to_api conversion")
    print("=" * 70)

    # Test SaveVideo conversion
    print("\n1. Testing SaveVideo widget mapping...")
    graph = {
        "nodes": [
            # Source node that provides VIDEO
            {
                "id": 88,
                "type": "CreateVideo",
                "mode": 0,
                "inputs": [{"name": "images", "link": None}],
                "outputs": [{"name": "VIDEO", "type": "VIDEO", "links": [147]}],
                "widgets_values": [16],
            },
            # SaveVideo node
            {
                "id": 80,
                "type": "SaveVideo",
                "mode": 0,
                "inputs": [{"name": "video", "link": 147}],
                "widgets_values": ["video/ComfyUI", "auto", "auto"],
            }
        ],
        "links": [[147, 88, 0, 80, 0, "VIDEO"]],
    }
    api = graph_to_api(graph, OBJECT_INFO)
    inputs = api.get("80", {}).get("inputs", {})

    if "codec" in inputs and "format" in inputs:
        print("   OK: SaveVideo has codec and format")
        print(f"   filename_prefix={inputs.get('filename_prefix')}")
        print(f"   codec={inputs.get('codec')}")
        print(f"   format={inputs.get('format')}")
    else:
        print("   FAIL: SaveVideo missing codec or format!")
        print(f"   inputs={inputs}")

    # Test real template
    print("\n2. Testing video_wan2_2_14B_t2v template...")
    try:
        path = get_template_path("video_wan2_2_14B_t2v")
        with open(path) as f:
            graph = json.load(f)
        api = graph_to_api(graph, OBJECT_INFO)

        save_videos = [(k, v) for k, v in api.items() if v["class_type"] == "SaveVideo"]
        all_ok = True
        for node_id, node in save_videos:
            inputs = node["inputs"]
            has_codec = "codec" in inputs
            has_format = "format" in inputs
            if has_codec and has_format:
                print(f"   OK: SaveVideo {node_id} has codec={inputs['codec']}, format={inputs['format']}")
            else:
                print(f"   FAIL: SaveVideo {node_id} missing codec={has_codec}, format={has_format}")
                all_ok = False

        if all_ok:
            print("   All SaveVideo nodes OK!")
        else:
            print("   SOME SAVEVIDEO NODES FAILED!")

    except FileNotFoundError:
        print("   SKIPPED: template not found")
    except Exception as e:
        print(f"   ERROR: {e}")
