"""
Compute3 API services - key verification and model listing.
"""

import logging
import httpx
from config import API_BASE_URL

logger = logging.getLogger(__name__)


async def verify_api_key(api_key: str) -> dict | None:
    """
    Verify API key by calling /user endpoint.
    Returns user info dict if valid, None if invalid.
    """
    async with httpx.AsyncClient() as client:
        try:
            url = f"{API_BASE_URL}/api/user"
            logger.debug(f"Verifying API key at {url}")
            resp = await client.get(
                url,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10.0,
            )
            logger.debug(f"API key verification response: {resp.status_code} {resp.text[:200]}")
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception as e:
            logger.debug(f"API key verification error: {e}")
            return None


async def list_models(api_key: str) -> list[str]:
    """
    Fetch available models from /v1/models endpoint.
    Returns list of model IDs.
    """
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{API_BASE_URL}/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                # OpenAI-compatible format: {"data": [{"id": "model-name", ...}]}
                return [m["id"] for m in data.get("data", [])]
            return []
        except Exception:
            return []
