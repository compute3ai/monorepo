#!/usr/bin/env python3
"""
Generate MDX documentation for ComfyUI workflow templates.

Usage:
    # Generate from templates.txt (default) with playground.json output
    python gen_template_docs.py \
        -o ../site/apps/main/content/comfyui \
        --public ../site/apps/main/public/comfyui \
        --playground-json ../site/apps/main/public/playground.json

    # Generate specific templates
    python gen_template_docs.py -t video_wan2_2_14B_t2v flux_schnell \
        -o ../site/apps/main/content/comfyui \
        --public ../site/apps/main/public/comfyui

    # List available templates
    python gen_template_docs.py --list

Input:
    templates.txt - List of template IDs to generate (one per line, # comments)

Output structure:
    content/comfyui/
    ├── {template_id}/
    │   └── index.mdx
    └── index.json

    public/comfyui/
    └── {template_id}/
        └── thumbnail.webp

    public/playground.json  (optional, same as index.json)
"""
import argparse
import json
import re
import shutil
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Optional

from PIL import Image
from comfyui_workflow_templates import get_asset_path, iter_templates

THUMBNAIL_WIDTH = 640  # Resize thumbnails to this width (higher = better quality)
THUMBNAIL_QUALITY = 90  # WebP quality (higher = better quality)


@dataclass
class TemplateParam:
    """A configurable parameter extracted from the workflow."""
    name: str
    type: str  # string, int, float, enum
    default: any
    description: str = ""
    node_type: str = ""
    options: list = field(default_factory=list)  # For enums


@dataclass
class TemplateModel:
    """A model required by the workflow."""
    filename: str
    loader_type: str  # UNETLoader, CLIPLoader, VAELoader, LoraLoaderModelOnly
    url: str = ""  # Huggingface URL if available


@dataclass
class TemplateInfo:
    """All extracted info about a template."""
    template_id: str
    bundle: str
    version: str

    # Extracted from workflow
    output_type: str  # video, image, animation
    description: str  # From Note/MarkdownNote nodes (long technical description)
    example_prompt: str
    negative_prompt: str

    params: list[TemplateParam] = field(default_factory=list)
    models: list[TemplateModel] = field(default_factory=list)
    assets: list[str] = field(default_factory=list)  # Preview image filenames

    # For card display (from upstream index.json)
    thumbnail: str = ""  # Primary preview image filename
    title: str = ""  # Human-readable title
    card_description: str = ""  # Short description for cards
    tags: list[str] = field(default_factory=list)
    tutorial_url: str = ""
    date: str = ""
    size: int = 0
    media_type: str = ""  # image, video, audio

    # Raw data for debugging
    node_types: dict = field(default_factory=dict)


def load_upstream_index(index_path: Path = None) -> dict[str, dict]:
    """Load upstream index.json and return a dict mapping template name to metadata.

    If no path provided, auto-discovers index.json files from installed
    comfyui_workflow_templates_* packages.
    """
    templates = {}

    if index_path:
        # Load from explicit path
        if not index_path.exists():
            print(f"Warning: upstream index not found at {index_path}")
            return {}

        with open(index_path) as f:
            data = json.load(f)

        for category in data:
            for template in category.get("templates", []):
                name = template.get("name")
                if name:
                    templates[name] = template
    else:
        # Auto-discover from installed packages
        import importlib
        import pkgutil

        for finder, name, ispkg in pkgutil.iter_modules():
            if name.startswith("comfyui_workflow_templates_media"):
                try:
                    mod = importlib.import_module(name)
                    pkg_path = Path(mod.__file__).parent
                    index_file = pkg_path / "templates" / "index.json"

                    if index_file.exists():
                        with open(index_file) as f:
                            data = json.load(f)

                        for category in data:
                            for template in category.get("templates", []):
                                tname = template.get("name")
                                if tname:
                                    templates[tname] = template
                except Exception as e:
                    print(f"Warning: failed to load index from {name}: {e}")

    return templates


def extract_template_info(template_id: str, upstream_index: dict[str, dict] = None) -> TemplateInfo:
    """Extract all useful information from a template workflow.

    Args:
        template_id: The template identifier
        upstream_index: Optional dict from load_upstream_index() with metadata
    """
    upstream_index = upstream_index or {}

    # Find template entry
    entry = None
    for t in iter_templates():
        if t.template_id == template_id:
            entry = t
            break

    if not entry:
        raise ValueError(f"Template not found: {template_id}")

    # Load workflow JSON
    workflow_path = get_asset_path(template_id, f"{template_id}.json")
    with open(workflow_path) as f:
        wf = json.load(f)

    info = TemplateInfo(
        template_id=template_id,
        bundle=entry.bundle,
        version=entry.version,
        output_type="unknown",
        description="",
        example_prompt="",
        negative_prompt="",
    )

    # Collect assets (preview images)
    for asset in entry.assets:
        if asset.filename.endswith(('.webp', '.png', '.jpg', '.gif', '.mp4')):
            if asset.filename != f"{template_id}.json":
                info.assets.append(asset.filename)

    # Set thumbnail (first image) and title
    if info.assets:
        info.thumbnail = info.assets[0]

    # Get metadata from upstream index if available
    upstream = upstream_index.get(template_id, {})
    info.title = upstream.get("title") or _format_title(template_id)
    info.card_description = upstream.get("description", "")
    info.tags = upstream.get("tags", [])
    info.tutorial_url = upstream.get("tutorialUrl", "")
    info.date = upstream.get("date", "")
    info.size = upstream.get("size", 0)
    info.media_type = upstream.get("mediaType", "")

    # Index nodes by type
    nodes_by_type: dict[str, list] = {}
    for node in wf.get("nodes", []):
        node_type = node.get("type", "unknown")
        if node_type not in nodes_by_type:
            nodes_by_type[node_type] = []
        nodes_by_type[node_type].append(node)

    info.node_types = {k: len(v) for k, v in nodes_by_type.items()}

    # Determine output type
    if "SaveVideo" in nodes_by_type:
        info.output_type = "video"
    elif "SaveAnimatedWEBP" in nodes_by_type or "SaveAnimatedPNG" in nodes_by_type:
        info.output_type = "animation"
    elif "SaveImage" in nodes_by_type:
        info.output_type = "image"
    elif "Save3D" in nodes_by_type or "Hunyuan3DGLBExport" in nodes_by_type or info.template_id.startswith("3d_") or "hunyuan3d" in info.template_id.lower():
        info.output_type = "3D"

    # Extract description from Note/MarkdownNote nodes
    descriptions = []
    for node_type in ["MarkdownNote", "Note"]:
        for node in nodes_by_type.get(node_type, []):
            widgets = node.get("widgets_values", [])
            title = node.get("title", "")
            if widgets and isinstance(widgets[0], str):
                text = widgets[0].strip()
                if text and len(text) > 10:  # Skip short notes
                    descriptions.append(f"**{title}**\n{text}" if title else text)
    info.description = "\n\n".join(descriptions)

    # Extract prompts from CLIPTextEncode
    for node in nodes_by_type.get("CLIPTextEncode", []):
        title = node.get("title", "").lower()
        widgets = node.get("widgets_values", [])
        if widgets and isinstance(widgets[0], str):
            text = widgets[0]
            if "positive" in title and not info.example_prompt:
                info.example_prompt = text
            elif "negative" in title and not info.negative_prompt:
                info.negative_prompt = text

    # Extract params from various nodes
    _extract_latent_params(info, nodes_by_type)
    _extract_sampler_params(info, nodes_by_type)
    _extract_save_params(info, nodes_by_type)

    # Extract models
    _extract_models(info, nodes_by_type)

    return info


def _extract_latent_params(info: TemplateInfo, nodes_by_type: dict):
    """Extract width/height/length from Empty*Latent* nodes."""
    latent_types = [
        "EmptyLatentImage", "EmptySD3LatentImage", "EmptyFlux2LatentImage",
        "EmptyHunyuanLatentVideo", "EmptyMochiLatentVideo", "EmptyLTXVLatentVideo",
    ]

    for lt in latent_types:
        for node in nodes_by_type.get(lt, []):
            widgets = node.get("widgets_values", [])
            if len(widgets) >= 2:
                info.params.append(TemplateParam(
                    name="width", type="int", default=widgets[0],
                    description="Output width in pixels", node_type=lt
                ))
                info.params.append(TemplateParam(
                    name="height", type="int", default=widgets[1],
                    description="Output height in pixels", node_type=lt
                ))
            if len(widgets) >= 3 and "Video" in lt:
                info.params.append(TemplateParam(
                    name="length", type="int", default=widgets[2],
                    description="Video length in frames", node_type=lt
                ))
            return  # Only use first latent node


def _extract_sampler_params(info: TemplateInfo, nodes_by_type: dict):
    """Extract steps/cfg/seed/sampler from KSampler* nodes."""
    sampler_types = ["KSampler", "KSamplerAdvanced", "SamplerCustom"]

    for st in sampler_types:
        for node in nodes_by_type.get(st, []):
            widgets = node.get("widgets_values", [])
            if not widgets:
                continue

            if st == "KSampler" and len(widgets) >= 6:
                # KSampler: seed, control, steps, cfg, sampler_name, scheduler, denoise
                info.params.append(TemplateParam(
                    name="seed", type="int", default=widgets[0],
                    description="Random seed (use -1 for random)", node_type=st
                ))
                info.params.append(TemplateParam(
                    name="steps", type="int", default=widgets[2],
                    description="Number of sampling steps", node_type=st
                ))
                info.params.append(TemplateParam(
                    name="cfg", type="float", default=widgets[3],
                    description="CFG scale (guidance strength)", node_type=st
                ))
                info.params.append(TemplateParam(
                    name="sampler_name", type="enum", default=widgets[4],
                    description="Sampler algorithm", node_type=st
                ))
                info.params.append(TemplateParam(
                    name="scheduler", type="enum", default=widgets[5],
                    description="Noise scheduler", node_type=st
                ))
                return

            elif st == "KSamplerAdvanced" and len(widgets) >= 10:
                # KSamplerAdvanced: add_noise, seed, control, steps, cfg, sampler, scheduler, start, end, return_noise
                info.params.append(TemplateParam(
                    name="seed", type="int", default=widgets[1],
                    description="Random seed", node_type=st
                ))
                info.params.append(TemplateParam(
                    name="steps", type="int", default=widgets[3],
                    description="Number of sampling steps", node_type=st
                ))
                info.params.append(TemplateParam(
                    name="cfg", type="float", default=widgets[4],
                    description="CFG scale (guidance strength)", node_type=st
                ))
                info.params.append(TemplateParam(
                    name="sampler_name", type="enum", default=widgets[5],
                    description="Sampler algorithm", node_type=st
                ))
                info.params.append(TemplateParam(
                    name="scheduler", type="enum", default=widgets[6],
                    description="Noise scheduler", node_type=st
                ))
                return


def _extract_save_params(info: TemplateInfo, nodes_by_type: dict):
    """Extract output filename prefix from Save* nodes."""
    save_types = ["SaveVideo", "SaveImage", "SaveAnimatedWEBP", "SaveAnimatedPNG"]

    for st in save_types:
        for node in nodes_by_type.get(st, []):
            widgets = node.get("widgets_values", [])
            if widgets and isinstance(widgets[0], str):
                info.params.append(TemplateParam(
                    name="filename_prefix", type="string", default=widgets[0],
                    description="Output filename prefix", node_type=st
                ))
                return


def _extract_models(info: TemplateInfo, nodes_by_type: dict):
    """Extract required models from loader nodes."""
    loader_types = {
        "UNETLoader": 0,      # unet_name is first widget
        "CheckpointLoaderSimple": 0,  # ckpt_name
        "CLIPLoader": 0,      # clip_name
        "VAELoader": 0,       # vae_name
        "LoraLoaderModelOnly": 1,  # lora_name is second (after model connection)
        "LoraLoader": 1,
    }

    seen = set()
    for loader_type, name_idx in loader_types.items():
        for node in nodes_by_type.get(loader_type, []):
            widgets = node.get("widgets_values", [])
            if len(widgets) > name_idx:
                filename = widgets[name_idx]
                if isinstance(filename, str) and filename not in seen:
                    seen.add(filename)
                    # Try to get URL from node properties
                    url = ""
                    props = node.get("properties", {})
                    models_list = props.get("models", [])
                    for m in models_list:
                        if m.get("name") == filename:
                            url = m.get("url", "")
                            # Clean up the URL (remove ?download=true)
                            if url and "?" in url:
                                url = url.split("?")[0]
                            break
                    info.models.append(TemplateModel(
                        filename=filename,
                        loader_type=loader_type,
                        url=url
                    ))


def copy_thumbnail(src_path: str, dst_path: Path, resize_width: int = None) -> None:
    """Copy thumbnail to destination, optionally resizing.

    By default just copies the file to preserve animations.
    If resize_width is set, resizes (but loses animation).
    """
    if resize_width:
        with Image.open(src_path) as img:
            ratio = resize_width / img.width
            height = int(img.height * ratio)
            resized = img.resize((resize_width, height), Image.Resampling.LANCZOS)
            resized.save(dst_path, "WEBP", quality=THUMBNAIL_QUALITY)
    else:
        # Just copy the file to preserve animations
        shutil.copy2(src_path, dst_path)


def generate_mdx(info: TemplateInfo, output_dir: Path, public_dir: Path = None, resize_width: int = None) -> Path:
    """Generate MDX file and thumbnail for a template.

    Args:
        info: Template metadata
        output_dir: Directory for MDX files (content/comfyui/)
        public_dir: Directory for thumbnails (public/comfyui/), if None uses output_dir
        resize_width: Optional width to resize thumbnails (None = copy as-is)

    Output structure:
        content/comfyui/{template_id}/index.mdx
        public/comfyui/{template_id}/thumbnail.webp
    """
    # Create template directory for MDX
    template_dir = output_dir / info.template_id
    template_dir.mkdir(parents=True, exist_ok=True)

    # Determine thumbnail path (public or same as content)
    if public_dir:
        thumb_dir = public_dir / info.template_id
        thumb_dir.mkdir(parents=True, exist_ok=True)
        # Reference from public root: /comfyui/{template_id}/thumbnail.webp
        thumb_ref = f"/comfyui/{info.template_id}/thumbnail.webp"
    else:
        thumb_dir = template_dir
        thumb_ref = "./thumbnail.webp"

    # Build frontmatter
    frontmatter = {
        "title": info.title,
        "description": info.card_description,  # Short description for cards
        "template_id": info.template_id,
        "bundle": info.bundle,
        "output_type": info.output_type,
        "thumbnail": thumb_ref if info.thumbnail else None,
        "tags": info.tags if info.tags else None,
        "tutorial_url": info.tutorial_url if info.tutorial_url else None,
        "date": info.date if info.date else None,
        "models": [m.filename for m in info.models],
    }

    # Build MDX content
    lines = [
        "---",
        *[f"{k}: {json.dumps(v)}" for k, v in frontmatter.items() if v is not None],
        "---",
        "",
        f"# {frontmatter['title']}",
        "",
    ]

    # Preview thumbnail
    if info.thumbnail:
        lines.append(f"![thumbnail]({thumb_ref})")
        lines.append("")

    # Description from notes
    if info.description:
        lines.append("## About")
        lines.append("")
        lines.append(info.description)
        lines.append("")

    # Parameters table
    if info.params:
        lines.append("## Parameters")
        lines.append("")
        lines.append("| Parameter | Type | Default | Description |")
        lines.append("|-----------|------|---------|-------------|")

        # Dedupe params by name (take first)
        seen_params = set()
        for p in info.params:
            if p.name in seen_params:
                continue
            seen_params.add(p.name)
            default_str = json.dumps(p.default) if not isinstance(p.default, str) else p.default
            if len(default_str) > 30:
                default_str = default_str[:27] + "..."
            lines.append(f"| `{p.name}` | {p.type} | `{default_str}` | {p.description} |")
        lines.append("")

    # Example prompts
    if info.example_prompt:
        lines.append("## Example Prompt")
        lines.append("")
        lines.append("```")
        lines.append(info.example_prompt)
        lines.append("```")
        lines.append("")

    if info.negative_prompt:
        lines.append("## Default Negative Prompt")
        lines.append("")
        lines.append("```")
        lines.append(info.negative_prompt)
        lines.append("```")
        lines.append("")

    # CLI usage
    lines.append("## Usage")
    lines.append("")
    lines.append("```bash")
    cmd = f'c3 comfyui run {info.template_id} \\\n  --prompt "your prompt here" \\\n  --output my_output'

    # Add key params with their defaults
    seen_params = set()
    for p in info.params:
        if p.name in seen_params:
            continue
        seen_params.add(p.name)
        if p.name in ("steps", "cfg", "width", "height"):
            cmd += f" \\\n  --{p.name} {p.default}"

    lines.append(cmd)
    lines.append("```")
    lines.append("")

    # Models required
    if info.models:
        lines.append("## Required Models")
        lines.append("")
        for m in info.models:
            if m.url:
                lines.append(f"- [{m.filename}]({m.url}) ({m.loader_type})")
            else:
                lines.append(f"- `{m.filename}` ({m.loader_type})")
        lines.append("")

    # Write MDX file
    mdx_path = template_dir / "index.mdx"
    mdx_path.write_text("\n".join(lines))

    # Copy thumbnail (optionally resize)
    if info.thumbnail:
        try:
            src = get_asset_path(info.template_id, info.thumbnail)
            dst = thumb_dir / "thumbnail.webp"
            copy_thumbnail(src, dst, resize_width=resize_width)
        except Exception as e:
            print(f"  Warning: Could not create thumbnail: {e}")

    return mdx_path


def _format_title(template_id: str) -> str:
    """Convert template_id to human-readable title."""
    # video_wan2_2_14B_t2v -> Wan 2.2 14B Text-to-Video
    title = template_id.replace("_", " ").replace("-", " ")

    # Common substitutions
    subs = {
        "t2v": "Text-to-Video",
        "i2v": "Image-to-Video",
        "t2i": "Text-to-Image",
        "i2i": "Image-to-Image",
        "wan2 2": "Wan 2.2",
        "wan 2 2": "Wan 2.2",
        "14b": "14B",
        "1 3b": "1.3B",
        "flux": "Flux",
        "sdxl": "SDXL",
        "sd3": "SD3",
        "video": "Video",
        "image": "Image",
        "api": "API",
    }

    for old, new in subs.items():
        title = re.sub(rf'\b{old}\b', new, title, flags=re.IGNORECASE)

    return title.strip().title()


def load_templates_txt(path: Path) -> list[str]:
    """Load template IDs from a text file (one per line, # comments ignored)."""
    if not path.exists():
        return []

    templates = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                templates.append(line)
    return templates


def main():
    parser = argparse.ArgumentParser(
        description="Generate MDX docs for ComfyUI templates",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate from templates.txt (default)
  %(prog)s -o ../site/apps/main/content/comfyui \\
      --public ../site/apps/main/public/comfyui

  # Generate specific templates with thumbnails to public/
  %(prog)s -t video_wan2_2_14B_t2v flux_schnell \\
      -o ../site/apps/main/content/comfyui \\
      --public ../site/apps/main/public/comfyui

  # List available templates
  %(prog)s --list
        """
    )
    parser.add_argument("--templates", "-t", nargs="+", help="Template IDs to generate docs for")
    parser.add_argument("--templates-file", "-f", default="templates.txt", help="File with template IDs (default: templates.txt)")
    parser.add_argument("--all", action="store_true", help="Generate docs for all templates (ignores templates.txt)")
    parser.add_argument("--bundle", "-b", help="Filter by bundle (e.g., media-video)")
    parser.add_argument("--output-dir", "-o", default="./content/comfyui", help="Output directory for MDX files")
    parser.add_argument("--public", "-p", help="Output directory for thumbnails (public/comfyui/)")
    parser.add_argument("--playground-json", help="Output path for playground.json (e.g., public/playground.json)")
    parser.add_argument("--index", "-i", help="Path to upstream index.json for titles/descriptions")
    parser.add_argument("--resize", "-r", type=int, metavar="WIDTH", help="Resize thumbnails to WIDTH (default: copy as-is to preserve animations)")
    parser.add_argument("--list", "-l", action="store_true", help="List available templates")

    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    public_dir = Path(args.public) if args.public else None
    resize_width = args.resize

    # Load upstream index for metadata (auto-discover if not specified)
    if args.index:
        upstream_index = load_upstream_index(Path(args.index))
        print(f"Loaded {len(upstream_index)} templates from {args.index}")
    else:
        upstream_index = load_upstream_index()
        if upstream_index:
            print(f"Auto-discovered {len(upstream_index)} templates from installed packages")

    # List mode
    if args.list:
        templates = list(iter_templates())
        bundles: dict[str, list] = {}
        for t in templates:
            if t.bundle not in bundles:
                bundles[t.bundle] = []
            bundles[t.bundle].append(t.template_id)

        for bundle, ids in sorted(bundles.items()):
            print(f"\n{bundle} ({len(ids)} templates):")
            for tid in sorted(ids):
                print(f"  {tid}")
        return

    # Get templates to process
    template_ids = []
    if args.templates:
        template_ids = args.templates
    elif args.all:
        for t in iter_templates():
            if args.bundle and t.bundle != args.bundle:
                continue
            template_ids.append(t.template_id)
    else:
        # Default: read from templates.txt
        script_dir = Path(__file__).parent
        templates_file = script_dir / args.templates_file
        template_ids = load_templates_txt(templates_file)
        if not template_ids:
            print(f"No templates found in {templates_file}")
            parser.print_help()
            return
        print(f"Loaded {len(template_ids)} templates from {templates_file}")

    print(f"Generating docs for {len(template_ids)} templates...")
    if public_dir:
        print(f"  MDX -> {output_dir}")
        print(f"  Thumbnails -> {public_dir}")

    # Collect index data
    index_data = []

    for template_id in template_ids:
        try:
            print(f"  {template_id}...")
            info = extract_template_info(template_id, upstream_index)

            # Generate MDX + thumbnail
            mdx_path = generate_mdx(info, output_dir, public_dir, resize_width=resize_width)
            print(f"    -> {mdx_path}")

            # Collect for index
            index_data.append({
                "template_id": info.template_id,
                "title": info.title,
                "description": info.card_description,
                "bundle": info.bundle,
                "output_type": info.output_type,
                "tags": info.tags,
            })

        except Exception as e:
            print(f"    ERROR: {e}")

    # Write index.json
    if index_data:
        index_content = {
            "templates": index_data,
            "bundles": sorted(set(t["bundle"] for t in index_data)),
            "count": len(index_data),
        }

        index_path = output_dir / "index.json"
        with open(index_path, "w") as f:
            json.dump(index_content, f, indent=2)
        print(f"\nIndex: {index_path}")

        # Also write playground.json if requested
        if args.playground_json:
            playground_path = Path(args.playground_json)
            playground_path.parent.mkdir(parents=True, exist_ok=True)
            with open(playground_path, "w") as f:
                json.dump(index_content, f, indent=2)
            print(f"Playground: {playground_path}")

    print(f"\nDone! Output in {output_dir}")


if __name__ == "__main__":
    main()
