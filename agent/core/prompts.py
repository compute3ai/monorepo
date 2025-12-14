"""
System prompts for the agent.

Provides base prompt templates that frontends can customize.
"""


def build_system_prompt(
    webhook_secret: str | None = None,
    extra_instructions: str | None = None,
) -> str:
    """
    Build the system prompt for the agent.

    Args:
        webhook_secret: Unused, kept for backward compatibility (notify_url is now injected automatically)
        extra_instructions: Optional frontend-specific instructions to append

    Returns:
        Complete system prompt string
    """
    prompt = """You are a helpful AI assistant with access to GPU compute tools.

TOOL USAGE:
1. Use each tool ONCE - do NOT call the same tool multiple times
2. After using tools, provide a brief SUMMARY of what you did

IMAGE/VIDEO GENERATION:
Use the flow_* tools to generate images and videos:
- flow_text_to_image: Generate images with Qwen-Image (good text rendering)
- flow_text_to_image_hidream: Generate images with HiDream (highest quality)
- flow_text_to_video: Generate videos with Wan 2.2 14B
- flow_image_to_video: Animate an image into video
- flow_speaking_video: Create lip-sync video from image + audio

Simply provide the prompt and any parameters. The result will be sent back to this chat automatically when complete."""

    if extra_instructions:
        prompt += f"\n\n{extra_instructions}"

    return prompt
