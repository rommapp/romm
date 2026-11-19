import tempfile
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import IO, Any, Final

from config import ROM_UPLOAD_TMP_BASE
from handler.metadata.mame_index import (
    MAME_LATEST_RELEASE_API,
    MAME_LISTXML_ASSET_RE,
    iter_listxml,
    write_index,
)
from logger.logger import log
from tasks.registry import UPDATE_MAME_INDEX_SPEC
from tasks.tasks import PeriodicTask
from utils.context import ctx_httpx_client, initialize_context

from . import UpdateStats

# Where an uploaded listxml waits for the task that imports it.
MAME_UPLOAD_PATH: Final = ROM_UPLOAD_TMP_BASE.parent / "mame" / "listxml.upload"

DOWNLOAD_TIMEOUT: Final = 600


async def latest_listxml_url() -> str:
    """The `mameNNNNlx.zip` asset of MAME's latest GitHub release."""
    client = ctx_httpx_client.get()
    response = await client.get(
        MAME_LATEST_RELEASE_API,
        headers={"Accept": "application/vnd.github+json"},
        timeout=60,
    )
    response.raise_for_status()
    for asset in response.json().get("assets", []):
        if MAME_LISTXML_ASSET_RE.match(asset.get("name", "")):
            return str(asset["browser_download_url"])
    raise RuntimeError("MAME's latest release has no listxml zip")


async def download_to(url: str, target: IO[bytes]) -> None:
    """Stream a file to disk, since an unzipped listxml runs past 250MB."""
    import httpx2

    client = ctx_httpx_client.get()
    try:
        async with client.stream(
            "GET", url, timeout=DOWNLOAD_TIMEOUT, follow_redirects=True
        ) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes():
                target.write(chunk)
    except httpx2.HTTPStatusError as exc:
        raise RuntimeError(f"{url} answered {exc.response.status_code}") from exc
    except httpx2.HTTPError as exc:
        reason = str(exc) or type(exc).__name__
        raise RuntimeError(f"Could not reach {url}: {reason}") from exc
    target.flush()


@contextmanager
def open_listxml(path: Path) -> Iterator[IO[bytes]]:
    """The XML inside `path`, a plain listxml or a zip holding one."""
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            members = [n for n in archive.namelist() if n.lower().endswith(".xml")]
            if not members:
                raise ValueError("The zip holds no .xml file")
            # A release zip holds just the one; otherwise take the largest.
            member = max(members, key=lambda n: archive.getinfo(n).file_size)
            with archive.open(member) as xml:
                yield xml
    else:
        with open(path, "rb") as xml:
            yield xml


class UpdateMameIndexTask(PeriodicTask):
    def __init__(self) -> None:
        super().__init__(UPDATE_MAME_INDEX_SPEC)

    @initialize_context()
    async def run(self, url: str | None = None, uploaded: bool = False) -> Any:
        """Load the MAME index from an uploaded file, a URL, or the latest release.

        Args:
            url: A listxml (or a zip of one) to download instead of the latest release.
            uploaded: Import the file the upload endpoint left at MAME_UPLOAD_PATH.
        """
        stats = UpdateStats()

        if uploaded:
            try:
                info = await self._import(MAME_UPLOAD_PATH, "upload", stats)
            finally:
                MAME_UPLOAD_PATH.unlink(missing_ok=True)
        else:
            source = url or await latest_listxml_url()
            log.info(f"Downloading the MAME listxml from {source}")
            with tempfile.NamedTemporaryFile(suffix=".mame") as tmp:
                await download_to(source, tmp)
                info = await self._import(Path(tmp.name), source, stats)

        log.info(f"MAME index loaded: {info['build']}, {info['sets']} sets")
        return stats.to_dict()

    async def _import(self, path: Path, source: str, stats: UpdateStats) -> Any:
        with open_listxml(path) as xml:
            return await write_index(
                iter_listxml(xml),
                source=source,
                on_progress=lambda count: stats.update(processed=count, total=count),
            )


update_mame_index_task = UpdateMameIndexTask()
