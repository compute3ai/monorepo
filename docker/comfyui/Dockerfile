# Define the version as a build argument
ARG COMFYUI_VERSION=v0.3.71

# Base downloader stage with common setup
FROM nvidia/cuda:12.6.3-cudnn-devel-ubuntu24.04

# Set CUDA architectures for building without GPUs
# Valid CUDA compute capabilities: 8.0 (A100), 8.6 (RTX 30xx), 8.7 (Jetson), 8.9 (RTX 40xx, L4, L40)
# Excludes Blackwell (9.0) and newer
ENV TORCH_CUDA_ARCH_LIST="8.0;8.6;8.7;8.9"

# Re-declare the ARG after FROM
ARG COMFYUI_VERSION

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Install Python and required packages
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    libgl1 \
    libglib2.0-0 \
    libgthread-2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Set up workspace directory
WORKDIR /app

# Create virtual environment
RUN python3 -m venv /app/venv

# Use shell form for commands that need to source the activation script
SHELL ["/bin/bash", "-c"]

# Install comfy-cli and required dependencies
RUN source /app/venv/bin/activate && \
    pip install --upgrade pip && \
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126 && \
    pip install triton && \
    pip install comfy-cli

# Build and install SageAttention2 from source (using our fork with GPU detection bypass)
RUN source /app/venv/bin/activate && \
    git clone https://github.com/comput3ai/SageAttention.git /tmp/SageAttention && \
    cd /tmp/SageAttention && \
    python setup.py install && \
    cd / && \
    rm -rf /tmp/SageAttention

# Install ComfyUI
RUN source /app/venv/bin/activate && comfy --skip-prompt --workspace /app/ComfyUI install --version $COMFYUI_VERSION --cuda-version 12.6 --nvidia

# Install additional dependencies for model downloading
RUN source /app/venv/bin/activate && \
    pip install huggingface_hub

# Create ComfyUI-Manager directory for config
RUN mkdir -p /app/ComfyUI/user/default/ComfyUI-Manager/

# Copy config.ini file
COPY config.ini /app/ComfyUI/user/default/ComfyUI-Manager/config.ini

# Expose port (default ComfyUI port is 8188)
EXPOSE 8188

# Copy download script and entrypoint (last to enable fast rebuilds)
COPY download.py /app/download.py
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/download.py /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
