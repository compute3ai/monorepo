"""
System prompts for the agent.

Provides base prompt templates that frontends can customize.
"""

from .models import get_model_config


BASE_PROMPT = """You are a helpful AI assistant that generates images and videos using GPU tools.

IMPORTANT RULES:
- Only call a tool when user gives a CLEAR instruction (e.g. "make this into a video", "edit this image to...")
- If user just sends a file without instructions, ASK what they want to do with it
- If instructions are unclear or incomplete, ASK for clarification before calling tools
- When user uploads files, file_ids are auto-injected - just provide the prompt parameter

After calling a tool, briefly tell the user what you're creating."""


def build_system_prompt(
    model: str = "",
    extra_instructions: str | None = None,
) -> str:
    """
    Build the system prompt for the agent.

    Args:
        model: Model name to get model-specific instructions
        extra_instructions: Optional frontend-specific instructions to append

    Returns:
        Complete system prompt string
    """
    prompt = BASE_PROMPT

    # Add model-specific instructions
    config = get_model_config(model)
    if config.tool_format_prompt:
        prompt += f"\n\n{config.tool_format_prompt}"

    if extra_instructions:
        prompt += f"\n\n{extra_instructions}"

    return prompt
