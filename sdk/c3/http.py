"""HTTP client utilities"""
import httpx
from typing import Any, Optional, Iterator
from dataclasses import dataclass


@dataclass
class APIError(Exception):
    """API error with status code and detail"""
    status_code: int
    detail: str

    def __str__(self):
        return f"API Error {self.status_code}: {self.detail}"


def _handle_response(response: httpx.Response) -> Any:
    """Handle API response, raise on error"""
    if response.status_code >= 400:
        try:
            detail = response.json().get("detail", response.text)
        except Exception:
            detail = response.text
        raise APIError(response.status_code, detail)
    if response.status_code == 204:
        return None
    return response.json()


class HTTPClient:
    """Sync HTTP client"""

    def __init__(self, base_url: str, api_key: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    @property
    def headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def get(self, path: str, params: dict = None) -> Any:
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(
                f"{self.base_url}{path}",
                headers=self.headers,
                params=params,
            )
            return _handle_response(response)

    def post(self, path: str, json: dict = None) -> Any:
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.base_url}{path}",
                headers=self.headers,
                json=json,
            )
            return _handle_response(response)

    def patch(self, path: str, json: dict = None) -> Any:
        with httpx.Client(timeout=self.timeout) as client:
            response = client.patch(
                f"{self.base_url}{path}",
                headers=self.headers,
                json=json,
            )
            return _handle_response(response)

    def delete(self, path: str) -> Any:
        with httpx.Client(timeout=self.timeout) as client:
            response = client.delete(
                f"{self.base_url}{path}",
                headers=self.headers,
            )
            return _handle_response(response)

    def stream_post(self, path: str, json: dict) -> Iterator[str]:
        """Streaming POST for SSE responses"""
        with httpx.Client(timeout=None) as client:
            with client.stream(
                "POST",
                f"{self.base_url}{path}",
                headers=self.headers,
                json=json,
            ) as response:
                if response.status_code >= 400:
                    raise APIError(response.status_code, response.read().decode())
                for line in response.iter_lines():
                    yield line
