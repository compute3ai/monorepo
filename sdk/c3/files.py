"""Files API"""
import os
import mimetypes
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .http import HTTPClient


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
            created_at=data.get("created_at"),
        )


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
        data = self._http.post_multipart("/api/files", files=files)
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
        data = self._http.post_multipart("/api/files", files=files)
        return File.from_dict(data)

    def get(self, file_id: str) -> File:
        """Get file metadata and URL.

        Args:
            file_id: The file ID

        Returns:
            File object with url for use in render calls
        """
        data = self._http.get(f"/api/files/{file_id}")
        return File.from_dict(data)

    def list(self, limit: int = 50, offset: int = 0) -> list[File]:
        """List your uploaded files.

        Args:
            limit: Max results (default 50)
            offset: Pagination offset

        Returns:
            List of File objects
        """
        params = {"limit": limit, "offset": offset}
        data = self._http.get("/api/files", params=params)
        items = data.get("items", [])
        return [File.from_dict(f) for f in items]

    def delete(self, file_id: str) -> dict:
        """Delete an uploaded file.

        Args:
            file_id: The file ID to delete

        Returns:
            {"status": "deleted", "id": "..."}
        """
        return self._http.delete(f"/api/files/{file_id}")
