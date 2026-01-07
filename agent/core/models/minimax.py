"""
Minimax model configuration.
"""

from .base import ModelConfig


class MinimaxConfig(ModelConfig):
    """Configuration for Minimax models (m2, m2.1, etc.)."""

    prefix = "minimax-"

    tool_format_prompt = ""
