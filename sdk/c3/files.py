"""Files API"""
import os
import time
import asyncio
import mimetypes
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .http import HTTPClient, AsyncHTTPClient


@dataclass
class File:
    """Uploaded file metadata.

    The `url` field is an internal reference (s3://...) that can only be used
    within the Compute3 platform (e.g., as image_url in render calls).
    It cannot be used for direct downloads or sharing.
    """
    id: str
    user_id: str
    filename: str
    content_type: str
    file_size: int
    url: str  # Internal S3 reference - only valid for use in C3 renders
    state: str | None = None  # processing, done, failed (for async uploads)
    error: str | None = None  # Error message if state=failed
    created_at: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "File":
        return cls(
            id=data.get("id", ""),
            user_id=data.get("user_id", ""),
            filename=data.get("filename", ""),
            content_type=data.get("content_type", ""),
            file_size=data.get("file_size", 0),
            url=data.get("url", ""),
            state=data.get("state"),
            error=data.get("error"),
            created_at=data.get("created_at"),
        )

    @property
    def is_ready(self) -> bool:
        """Check if file upload is complete and ready to use."""
        return self.state == "done"

    @property
    def is_failed(self) -> bool:
        """Check if file upload failed."""
        return self.state == "failed"

    @property
    def is_processing(self) -> bool:
        """Check if file upload is still processing."""
        return self.state == "processing"


class Files:
    """Files API wrapper for uploading assets"""

    def __init__(self, http: "HTTPClient"):
        self._http = http

    def upload(self, file_path: str) -> File:
        """Upload a file for use in renders.

        Args:
            file_path: Path to local file (image, audio, or video)

        Returns:
            File object with id and internal url for use in render calls.
            The url is an S3 reference that only works within C3.

        Example:
            file = c3.files.upload("./my_image.png")
            render = c3.renders.image_to_video("dancing", file.url)
        """
        # Read file
        with open(file_path, "rb") as f:
            content = f.read()

        filename = os.path.basename(file_path)

        # Guess content type
        content_type, _ = mimetypes.guess_type(file_path)
        if not content_type:
            content_type = "application/octet-stream"

        # Upload via multipart
        files = {"file": (filename, content, content_type)}
        data = self._http.post_multipart("/api/files/multi", files=files)
        return File.from_dict(data)

    def upload_bytes(self, content: bytes, filename: str, content_type: str) -> File:
        """Upload file bytes directly.

        Args:
            content: File bytes
            filename: Filename to use
            content_type: MIME type (e.g., "image/png", "audio/mp3")

        Returns:
            File object with id and url for use in render calls

        Example:
            file = c3.files.upload_bytes(image_bytes, "image.png", "image/png")
        """
        files = {"file": (filename, content, content_type)}
        data = self._http.post_multipart("/api/files/multi", files=files)
        return File.from_dict(data)

    def upload_url(self, url: str, path: str | None = None) -> File:
        """Upload a file from a URL (async backend processing).

        The backend downloads the file from the URL and uploads it to storage.
        Returns immediately with state=processing. Use wait_ready() or poll get().

        Args:
            url: The URL to download the file from
            path: Optional path prefix for organizing files

        Returns:
            File object with id and state=processing.

        Example:
            file = c3.files.upload_url("https://example.com/image.png")
            file = c3.files.wait_ready(file.id)  # Wait for completion
        """
        payload = {"url": url}
        if path:
            payload["path"] = path
        data = self._http.post("/api/files/url", json=payload)
        return File.from_dict(data)

    def upload_b64(
        self,
        data: str,
        filename: str,
        content_type: str | None = None,
        path: str | None = None,
    ) -> File:
        """Upload a file from base64-encoded data (async backend processing).

        The backend decodes the base64 data and uploads it to storage.
        Returns immediately with state=processing. Use wait_ready() or poll get().

        Args:
            data: Base64-encoded file content
            filename: Filename to use (e.g., "image.jpg")
            content_type: MIME type (auto-detected from filename if not provided)
            path: Optional path prefix for organizing files

        Returns:
            File object with id and state=processing.

        Example:
            import base64
            b64_data = base64.b64encode(image_bytes).decode()
            file = c3.files.upload_b64(b64_data, "image.png", "image/png")
            file = c3.files.wait_ready(file.id)
        """
        payload = {"data": data, "filename": filename}
        if content_type:
            payload["content_type"] = content_type
        if path:
            payload["path"] = path
        result = self._http.post("/api/files/b64", json=payload)
        return File.from_dict(result)

    def get(self, file_id: str) -> File:
        """Get file metadata and URL.

        Args:
            file_id: The file ID

        Returns:
            File object with url for use in render calls
        """
        data = self._http.get(f"/api/files/{file_id}")
        return File.from_dict(data)

    def delete(self, file_id: str) -> dict:
        """Delete an uploaded file.

        Args:
            file_id: The file ID to delete

        Returns:
            {"status": "deleted", "id": "..."}
        """
        return self._http.delete(f"/api/files/{file_id}")

    def wait_ready(
        self,
        file_id: str,
        timeout: float = 60.0,
        poll_interval: float = 1.0,
    ) -> File:
        """Wait for an async upload to complete.

        Polls the file status until it's done or failed.

        Args:
            file_id: The file ID to wait for
            timeout: Maximum time to wait in seconds
            poll_interval: Time between polls in seconds

        Returns:
            File object with final state (done or failed)

        Raises:
            TimeoutError: If file doesn't complete within timeout
            ValueError: If file upload failed

        Example:
            file = c3.files.upload_url("https://example.com/image.png")
            file = c3.files.wait_ready(file.id, timeout=30)
            print(f"Ready: {file.url}")
        """
        start = time.time()
        while time.time() - start < timeout:
            file = self.get(file_id)
            if file.is_ready:
                return file
            if file.is_failed:
                raise ValueError(f"File upload failed: {file.error}")
            time.sleep(poll_interval)
        raise TimeoutError(f"File {file_id} did not complete within {timeout}s")


class AsyncFiles:
    """Async Files API wrapper for uploading assets in async contexts.

    Use this in async applications like Telegram bots, web servers, etc.
    """

    def __init__(self, http: "AsyncHTTPClient"):
        self._http = http

    async def upload_bytes(
        self,
        content: bytes,
        filename: str,
        content_type: str,
        path: str | None = None,
    ) -> File:
        """Upload file bytes directly.

        Args:
            content: File bytes
            filename: Filename to use
            content_type: MIME type (e.g., "image/png", "audio/mp3")
            path: Optional path prefix for organizing files (e.g., "telegram/12345")

        Returns:
            File object with id and url for use in render calls

        Example:
            file = await files.upload_bytes(image_bytes, "photo.jpg", "image/jpeg")
        """
        files = {"file": (filename, content, content_type)}
        params = {"path": path} if path else None
        data = await self._http.post_multipart("/api/files/multi", files=files, params=params)
        return File.from_dict(data)

    async def upload_url(self, url: str, path: str | None = None) -> File:
        """Upload a file from a URL (async backend processing).

        The backend downloads the file from the URL and uploads it to storage.
        Returns immediately with state=processing. Use wait_ready() or poll get().

        Args:
            url: The URL to download the file from
            path: Optional path prefix for organizing files

        Returns:
            File object with id and state=processing.

        Example:
            file = await files.upload_url("https://example.com/image.png")
            file = await files.wait_ready(file.id)
        """
        payload = {"url": url}
        if path:
            payload["path"] = path
        data = await self._http.post("/api/files/url", json=payload)
        return File.from_dict(data)

    async def upload_b64(
        self,
        data: str,
        filename: str,
        content_type: str | None = None,
        path: str | None = None,
    ) -> File:
        """Upload a file from base64-encoded data (async backend processing).

        The backend decodes the base64 data and uploads it to storage.
        Returns immediately with state=processing. Use wait_ready() or poll get().

        Args:
            data: Base64-encoded file content
            filename: Filename to use (e.g., "image.jpg")
            content_type: MIME type (auto-detected from filename if not provided)
            path: Optional path prefix for organizing files

        Returns:
            File object with id and state=processing.

        Example:
            import base64
            b64_data = base64.b64encode(image_bytes).decode()
            file = await files.upload_b64(b64_data, "image.png", "image/png")
            file = await files.wait_ready(file.id)
        """
        payload = {"data": data, "filename": filename}
        if content_type:
            payload["content_type"] = content_type
        if path:
            payload["path"] = path
        result = await self._http.post("/api/files/b64", json=payload)
        return File.from_dict(result)

    async def get(self, file_id: str) -> File:
        """Get file metadata and URL.

        Args:
            file_id: The file ID

        Returns:
            File object with url for use in render calls
        """
        data = await self._http.get(f"/api/files/{file_id}")
        return File.from_dict(data)

    async def delete(self, file_id: str) -> dict:
        """Delete an uploaded file.

        Args:
            file_id: The file ID to delete

        Returns:
            {"status": "deleted", "id": "..."}
        """
        return await self._http.delete(f"/api/files/{file_id}")

    async def wait_ready(
        self,
        file_id: str,
        timeout: float = 60.0,
        poll_interval: float = 1.0,
    ) -> File:
        """Wait for an async upload to complete.

        Polls the file status until it's done or failed.

        Args:
            file_id: The file ID to wait for
            timeout: Maximum time to wait in seconds
            poll_interval: Time between polls in seconds

        Returns:
            File object with final state (done or failed)

        Raises:
            TimeoutError: If file doesn't complete within timeout
            ValueError: If file upload failed

        Example:
            file = await files.upload_url("https://example.com/image.png")
            file = await files.wait_ready(file.id, timeout=30)
            print(f"Ready: {file.url}")
        """
        import time
        start = time.time()
        while time.time() - start < timeout:
            file = await self.get(file_id)
            if file.is_ready:
                return file
            if file.is_failed:
                raise ValueError(f"File upload failed: {file.error}")
            await asyncio.sleep(poll_interval)
        raise TimeoutError(f"File {file_id} did not complete within {timeout}s")
