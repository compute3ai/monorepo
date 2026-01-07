"""
Model-specific configurations.
"""

from .base import ModelConfig
from .minimax import MinimaxConfig
from .glm4 import GLM4Config


# Order matters - first match wins
MODELS = [
    MinimaxConfig,
    GLM4Config,
]


def get_model_config(model: str) -> ModelConfig:
    """Get the configuration for a model by name."""
    for config_cls in MODELS:
        if config_cls.matches(model):
            return config_cls()
    return ModelConfig()


__all__ = ["get_model_config", "ModelConfig", "MinimaxConfig", "GLM4Config"]
