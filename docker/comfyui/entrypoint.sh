#!/bin/bash
set -e

echo "ComfyUI Container Starting..."
echo "=============================="

# Handle empty HF_TOKEN
if [ -z "${HF_TOKEN:-}" ]; then
    unset HF_TOKEN
fi

# Download templates if COMFYUI_TEMPLATES is set
if [ -n "${COMFYUI_TEMPLATES}" ]; then
    echo "Checking templates: ${COMFYUI_TEMPLATES}"
    source /app/venv/bin/activate && python3 /app/download.py
fi

# Start ComfyUI
echo ""
echo "Starting ComfyUI..."
echo "=============================="

exec /bin/bash -c "source /app/venv/bin/activate && comfy --workspace /app/ComfyUI launch -- --listen 0.0.0.0 --enable-cors-header --highvram"
