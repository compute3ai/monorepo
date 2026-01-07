"""
Base model configuration.
"""


class ModelConfig:
    """Base configuration for LLM models."""

    prefix: str = ""
    tool_format_prompt: str = ""

    @classmethod
    def matches(cls, model: str) -> bool:
        """Check if this config applies to the given model name."""
        return bool(cls.prefix) and model.lower().startswith(cls.prefix.lower())
