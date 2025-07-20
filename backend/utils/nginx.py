import dataclasses
from collections.abc import Collection
from typing import Any
from urllib.parse import quote

from anyio import Path
from fastapi.responses import Response


@dataclasses.dataclass(frozen=True)
class ZipContentLine:
    """Dataclass for lines returned in the response body, for usage with the `mod_zip` module.

    Reference:
    https://github.com/evanmiller/mod_zip?tab=readme-ov-file#usage
    """

    crc32: str | None
    size_bytes: int
    encoded_location: str
    filename: str

    def __str__(self) -> str:
        crc32 = self.crc32 or "-"
        return f"{crc32} {self.size_bytes} {self.encoded_location} {self.filename}"


class ZipResponse(Response):
    """Response class for returning a ZIP archive with multiple files, using the `mod_zip` module."""

    def __init__(
        self,
        *,
        content_lines: Collection[ZipContentLine],
        filename: str,
        **kwargs: Any,
    ):
        if kwargs.get("content"):
            raise ValueError(
                "Argument 'content' must not be provided, as it is generated from 'content_lines'"
            )

        kwargs["content"] = "\n".join(str(line) for line in content_lines)
        kwargs.setdefault("headers", {}).update(
            {
                "Content-Disposition": f"attachment; filename*=UTF-8''{filename}; filename=\"{filename}\"",
                "X-Archive-Files": "zip",
            }
        )

        super().__init__(**kwargs)


class FileRedirectResponse(Response):
    """Response class for serving a file download by using the X-Accel-Redirect header."""

    def __init__(
        self, *, download_path: Path, filename: str | None = None, **kwargs: Any
    ):
        """
        Arguments:
          - download_path: Path to the file to be served.
          - filename: Name of the file to be served. If not provided, the file name from the
              download_path is used.
        """
        media_type = kwargs.pop("media_type", "application/octet-stream")
        filename = filename or download_path.name
        kwargs.setdefault("headers", {}).update(
            {
                "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}; filename=\"{quote(filename)}\"",
                "X-Accel-Redirect": quote(str(download_path)),
            }
        )

        super().__init__(media_type=media_type, **kwargs)
