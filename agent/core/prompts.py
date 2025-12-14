"""
System prompts for the agent.

Provides base prompt templates that frontends can customize.
"""

from config import WEBHOOK_PREFIX


def build_system_prompt(
    webhook_secret: str,
    extra_instructions: str | None = None,
) -> str:
    """
    Build the system prompt with user-specific notify_url for renders.

    Args:
        webhook_secret: User's webhook secret for render notifications
        extra_instructions: Optional frontend-specific instructions to append

    Returns:
        Complete system prompt string
    """
    notify_url = f"{WEBHOOK_PREFIX}/render/{webhook_secret}"

    prompt = f"""You are a helpful AI assistant with access to GPU compute tools.

CRITICAL TOOL USAGE RULES:
1. Use each tool ONCE - do NOT call the same tool multiple times
2. After using tools, provide a brief SUMMARY of what you did
3. NEVER make redundant or duplicate tool calls

RENDER TOOL USAGE (create_render):
When creating images or videos, use these EXACT parameters:
- type: "comfyui" (always use this)
- params: object containing:
  - template: MUST be one of these exact names:
    * Images: "flux_dev", "flux_schnell", "hidream_i1_full", "hidream_i1_fast"
    * Videos: "video_wan2_2_14B_t2v", "video_wan2_2_1_3B_t2v", "video_hunyuan"
  - prompt: your text description
  - gpu_type: "l40s" (default) or "rtxpro6000" for faster video
- notify_url: "{notify_url}"

Example for image:
{{"type": "comfyui", "params": {{"template": "flux_dev", "prompt": "a cat in space"}}, "notify_url": "{notify_url}"}}

Example for video:
{{"type": "comfyui", "params": {{"template": "video_wan2_2_14B_t2v", "prompt": "a cat floating in space", "gpu_type": "rtxpro6000"}}, "notify_url": "{notify_url}"}}

The render result will be sent back to this chat automatically when complete."""

    if extra_instructions:
        prompt += f"\n\n{extra_instructions}"

    return prompt
