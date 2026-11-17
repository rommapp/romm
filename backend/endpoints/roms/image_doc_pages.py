"""HTTP plumbing shared by the image doc page routes of manuals and rom files."""

import asyncio
from pathlib import Path

from fastapi import HTTPException, status
from fastapi.responses import Response

from endpoints.responses.rom import ImageDocPagesSchema
from logger.logger import log
from utils.image_docs import (
    ImageDocError,
    ImageDocPageNotFoundError,
    list_image_doc_pages,
    read_image_doc_page,
)

# Page URLs carry the file's version, so a page never changes under one.
_PAGE_CACHE_CONTROL = "private, max-age=86400"


def _unreadable(exc: ImageDocError) -> HTTPException:
    log.error("Error reading image doc", exc_info=exc)
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail="The image doc could not be read",
    )


async def image_doc_pages(location: Path) -> ImageDocPagesSchema:
    try:
        pages = await asyncio.to_thread(list_image_doc_pages, location)
    except ImageDocError as exc:
        raise _unreadable(exc) from exc
    return ImageDocPagesSchema(count=len(pages))


async def image_doc_page_response(location: Path, page: int) -> Response:
    try:
        data, media_type = await asyncio.to_thread(read_image_doc_page, location, page)
    except ImageDocPageNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Page not found"
        ) from exc
    except ImageDocError as exc:
        raise _unreadable(exc) from exc
    return Response(
        content=data,
        media_type=media_type,
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": _PAGE_CACHE_CONTROL,
        },
    )
