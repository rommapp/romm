"""Page listing and reading for image docs: documents stored as an archive of
page images, the comic book archive formats (.cbz/.cbr)."""

import re
import zipfile
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Final

from utils.archives import ArchiveReadError, list_rar_file_members, read_rar_member
from utils.media_types import ALLOWED_IMAGE_EXTENSIONS, guess_media_file_type

# A page is held in memory while it is served, so a crafted archive can't
# inflate one past this.
MAX_IMAGE_DOC_PAGE_BYTES: Final = 64 * 1024 * 1024

_DIGITS: Final = re.compile(r"(\d+)")


class ImageDocError(Exception):
    """An image doc or one of its pages could not be read."""


class ImageDocPageNotFoundError(LookupError):
    """The archive has no page at the requested number."""


def _natural_key(name: str) -> list[int | str]:
    """Order `page2` before `page10`, as readers expect."""
    return [
        int(part) if part.isdigit() else part.lower() for part in _DIGITS.split(name)
    ]


def _is_page(name: str) -> bool:
    path = PurePosixPath(name.replace("\\", "/"))
    # macOS zips carry resource-fork twins of every image under __MACOSX.
    if any(part.startswith(".") or part == "__MACOSX" for part in path.parts):
        return False
    return path.suffix.lower() in ALLOWED_IMAGE_EXTENSIONS


def _member_names(path: Path) -> list[str]:
    # Extensions are often wrong (a .cbr that is really a zip), so the format
    # comes from the file's own signature.
    if zipfile.is_zipfile(path):
        try:
            with zipfile.ZipFile(path) as archive:
                return [
                    info.filename for info in archive.infolist() if not info.is_dir()
                ]
        except (zipfile.BadZipFile, OSError) as exc:
            raise ImageDocError(f"Error reading {path}: {exc}") from exc
    return [name for name, _size in list_rar_file_members(path)]


@lru_cache(maxsize=64)
def _cached_pages(path: str, _mtime_ns: int, _size: int) -> tuple[str, ...]:
    names = [name for name in _member_names(Path(path)) if _is_page(name)]
    return tuple(sorted(names, key=_natural_key))


def list_image_doc_pages(path: Path) -> tuple[str, ...]:
    """The archive's image members in reading order.

    Cached per file version, since every page request needs the listing.
    """
    try:
        stat = path.stat()
    except OSError as exc:
        raise ImageDocError(f"Error reading {path}: {exc}") from exc
    return _cached_pages(str(path), stat.st_mtime_ns, stat.st_size)


def _read_zip_member(path: Path, member: str) -> bytes:
    try:
        with zipfile.ZipFile(path) as archive:
            info = archive.getinfo(member)
            if info.file_size > MAX_IMAGE_DOC_PAGE_BYTES:
                raise ImageDocError(f"{member} in {path} is too large")
            with archive.open(info) as handle:
                data = handle.read(MAX_IMAGE_DOC_PAGE_BYTES + 1)
    except (zipfile.BadZipFile, KeyError, NotImplementedError, OSError) as exc:
        raise ImageDocError(f"Error reading {member} from {path}: {exc}") from exc
    # The header's size can lie; the bytes actually inflated can't.
    if len(data) > MAX_IMAGE_DOC_PAGE_BYTES:
        raise ImageDocError(f"{member} in {path} is too large")
    return data


def read_image_doc_page(path: Path, page: int) -> tuple[bytes, str]:
    """The image bytes and media type of a 1-based page.

    Raises:
        ImageDocPageNotFoundError: The archive has no such page.
        ImageDocError: The archive or page could not be read.
    """
    pages = list_image_doc_pages(path)
    if not 1 <= page <= len(pages):
        raise ImageDocPageNotFoundError(page)
    member = pages[page - 1]
    if zipfile.is_zipfile(path):
        data = _read_zip_member(path, member)
    else:
        try:
            data = read_rar_member(path, member, MAX_IMAGE_DOC_PAGE_BYTES)
        except ArchiveReadError as exc:
            raise ImageDocError(str(exc)) from exc
    return data, guess_media_file_type(member)
