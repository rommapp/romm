import dataclasses
from collections.abc import Collection
from typing import Any

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
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Archive-Files": "zip",
            }
        )

        super().__init__(**kwargs)
