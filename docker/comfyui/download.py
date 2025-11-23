#!/usr/bin/env python3
"""
Model downloader for ComfyUI Docker container - V2
Downloads ALL dependencies for a template, not just individual models
"""

import os
import sys
import json
from pathlib import Path
from huggingface_hub import hf_hub_download

def find_all_models_in_node(node):
    """Recursively find all model references in a node."""
    models = []

    def recurse(obj):
        if isinstance(obj, dict):
            # Check for the pattern: {name, url, directory}
            if 'url' in obj and 'directory' in obj and 'name' in obj:
                models.append({
                    'name': obj['name'],
                    'url': obj['url'],
                    'directory': obj['directory']
                })
            else:
                for value in obj.values():
                    recurse(value)
        elif isinstance(obj, list):
            for item in obj:
                recurse(item)

    recurse(node)
    return models

def get_template_dependencies(template_id):
    """Get all file dependencies for a template."""
    try:
        from comfyui_workflow_templates import iter_templates, get_asset_path
    except ImportError:
        print("Error: comfyui-workflow-templates not installed", flush=True)
        return []

    for template_entry in iter_templates():
        if template_entry.template_id == template_id:
            for asset in template_entry.assets:
                if asset.filename.endswith('.json'):
                    workflow_path = get_asset_path(template_entry.template_id, asset.filename)

                    with open(workflow_path, 'r') as f:
                        workflow = json.load(f)

                    nodes = workflow.get('nodes', [])

                    all_models = []
                    for node in nodes:
                        models = find_all_models_in_node(node)
                        all_models.extend(models)

                    return all_models

    return []

def parse_hf_url(url):
    """Parse HuggingFace URL to extract repo_id and filename."""
    # Example: https://huggingface.co/Comfy-Org/flux1-schnell/resolve/main/flux1-schnell-fp8.safetensors?download=true
    if 'huggingface.co' not in url:
        return None, None

    parts = url.split('/')
    try:
        idx = parts.index('huggingface.co')
        repo_id = f"{parts[idx+1]}/{parts[idx+2]}"
        # Find 'resolve' or 'blob'
        if 'resolve' in parts or 'blob' in parts:
            resolve_idx = parts.index('resolve') if 'resolve' in parts else parts.index('blob')
            # Skip 'main' or branch name
            filename = '/'.join(parts[resolve_idx+2:])
            # Remove query params
            filename = filename.split('?')[0]
            return repo_id, filename
    except (ValueError, IndexError):
        pass

    return None, None

def download_model(model_info, base_dir='/app/ComfyUI/models'):
    """Download a single model if it doesn't exist."""
    name = model_info['name']
    url = model_info['url']
    directory = model_info['directory']

    dest_dir = Path(base_dir) / directory
    dest_file = dest_dir / name

    if dest_file.exists():
        print(f"✓ Already exists: {name}", flush=True)
        return True

    print(f"\n{'='*80}", flush=True)
    print(f"Downloading: {name}", flush=True)
    print(f"Directory: {directory}", flush=True)
    print(f"URL: {url}", flush=True)
    print(f"{'='*80}\n", flush=True)

    repo_id, filename = parse_hf_url(url)

    if repo_id and filename:
        print(f"Using HuggingFace Hub: {repo_id} / {filename}", flush=True)
        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
            print(f"Starting download...", flush=True)
            # Download to cache first, then copy to destination
            # This avoids the local_dir preserving repo structure issue
            cached_path = hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                token=os.getenv('HF_TOKEN')
            )
            # Copy from cache to destination
            import shutil
            shutil.copy2(cached_path, dest_file)
            print(f"✓ Downloaded: {dest_file}", flush=True)
            return True
        except Exception as e:
            print(f"✗ Error: {e}", flush=True)
            return False
    else:
        print(f"Using direct download", flush=True)
        try:
            import urllib.request
            dest_dir.mkdir(parents=True, exist_ok=True)
            urllib.request.urlretrieve(url, dest_file)
            print(f"✓ Downloaded: {dest_file}", flush=True)
            return True
        except Exception as e:
            print(f"✗ Error: {e}", flush=True)
            return False

def main():
    """Main download logic."""
    templates = os.getenv('COMFYUI_TEMPLATES', '').strip()

    if not templates:
        print("No templates specified in COMFYUI_TEMPLATES environment variable", flush=True)
        return

    print("=" * 80, flush=True)
    print("ComfyUI Template Downloader V2", flush=True)
    print("=" * 80, flush=True)

    requested_templates = [t.strip() for t in templates.split(',') if t.strip()]
    print(f"\nRequested templates: {', '.join(requested_templates)}", flush=True)

    total_success = 0
    total_files = 0

    for template_id in requested_templates:
        print(f"\n{'='*80}", flush=True)
        print(f"Processing template: {template_id}", flush=True)
        print(f"{'='*80}", flush=True)

        dependencies = get_template_dependencies(template_id)

        if not dependencies:
            print(f"⚠ No dependencies found for template: {template_id}", flush=True)
            continue

        print(f"\nFound {len(dependencies)} files for {template_id}:", flush=True)
        for dep in dependencies:
            print(f"  - {dep['name']} ({dep['directory']})", flush=True)

        for dep in dependencies:
            total_files += 1
            if download_model(dep):
                total_success += 1

    print(f"\n{'='*80}", flush=True)
    print(f"Download complete: {total_success}/{total_files} files successful", flush=True)
    print(f"{'='*80}", flush=True)

if __name__ == "__main__":
    main()
