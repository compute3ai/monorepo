"""
GLM-4 model configuration.
"""

from .base import ModelConfig


class GLM4Config(ModelConfig):
    """Configuration for GLM-4 models (glm-4, glm4-7, etc.)."""

    prefix = "glm"

    tool_format_prompt = ""
