"""Server-side ROM patching helpers.

Shells out to the sibling ``patcher.js`` (Node.js + RomPatcher.js) to apply
a patch file to a ROM file.
"""

import asyncio
import copy
import json
import shutil
import zipfile
import zlib
from pathlib import Path

from anyio import Path as AnyioPath
from config import (
    ROM_PATCHER_MAX_CONCURRENCY,
    ROM_PATCHER_MAX_FILE_SIZE_BYTES,
    ROM_PATCHER_TIMEOUT,
)

from utils.filesystem import COMPRESSED_FILE_EXTENSIONS
from utils.zip_cache import ensure_zipfile_writable

PATCHER_SCRIPT = Path(__file__).parent / "patcher.js"

SUPPORTED_PATCH_EXTENSIONS = frozenset(
    (
        ".ips",
        ".ups",
        ".bps",
        ".ppf",
        ".rup",
        ".aps",
        ".bdf",
        ".pmsr",
        ".vcdiff",
        ".xdelta",
    )
)

# Bound concurrent operations because each Node subprocess loads a full ROM.
_patch_semaphore = asyncio.Semaphore(ROM_PATCHER_MAX_CONCURRENCY)

_WRITABLE_ZIP_COMPRESSION_TYPES = {
    zipfile.ZIP_STORED,
    zipfile.ZIP_DEFLATED,
    zipfile.ZIP_BZIP2,
    zipfile.ZIP_LZMA,
    zipfile.ZIP_ZSTANDARD,
}


class PatcherError(Exception):
    """Raised when the Node.js patcher script fails or produces no output."""


class PatcherInputError(PatcherError):
    """Raised when a ROM cannot be safely prepared for patching."""


def _extract_zip_member(
    archive_path: Path, output_path: Path, member_name: str | None
) -> str:
    try:
        with zipfile.ZipFile(archive_path, "r") as archive:
            members = [entry for entry in archive.infolist() if not entry.is_dir()]
            if not members:
                raise PatcherInputError("The ROM archive contains no files")

            if member_name is None:
                if len(members) != 1:
                    raise PatcherInputError(
                        "Select which file inside the ROM archive to patch"
                    )
                selected = members[0]
            else:
                matches = [entry for entry in members if entry.filename == member_name]
                if len(matches) != 1:
                    raise PatcherInputError(
                        "The selected file was not found uniquely in the ROM archive"
                    )
                selected = matches[0]

            if any(entry.flag_bits & 0x1 for entry in members):
                raise PatcherInputError("Encrypted ROM archives are not supported")
            if selected.file_size > ROM_PATCHER_MAX_FILE_SIZE_BYTES:
                raise PatcherInputError(
                    "The uncompressed ROM is too large to patch "
                    f"({selected.file_size} bytes, max {ROM_PATCHER_MAX_FILE_SIZE_BYTES})"
                )
            if (
                sum(entry.file_size for entry in members)
                > ROM_PATCHER_MAX_FILE_SIZE_BYTES
            ):
                raise PatcherInputError("The uncompressed ROM archive is too large")

            with (
                archive.open(selected, "r") as source,
                output_path.open("wb") as output,
            ):
                shutil.copyfileobj(source, output)
            if output_path.stat().st_size > ROM_PATCHER_MAX_FILE_SIZE_BYTES:
                output_path.unlink(missing_ok=True)
                raise PatcherInputError("The uncompressed ROM is too large to patch")
            return selected.filename
    except PatcherInputError:
        raise
    except (
        EOFError,
        OSError,
        RuntimeError,
        NotImplementedError,
        zipfile.BadZipFile,
        zlib.error,
    ) as e:
        raise PatcherInputError("The ROM archive could not be read") from e


def _rebuild_zip(
    archive_path: Path,
    output_path: Path,
    patched_path: Path,
    patched_member_name: str,
) -> None:
    try:
        ensure_zipfile_writable()
        with (
            zipfile.ZipFile(archive_path, "r") as source_archive,
            zipfile.ZipFile(output_path, "w", allowZip64=True) as output_archive,
        ):
            output_archive.comment = source_archive.comment
            for source_entry in source_archive.infolist():
                output_entry = copy.copy(source_entry)
                if (
                    output_entry.compress_type
                    not in _WRITABLE_ZIP_COMPRESSION_TYPES
                ):
                    output_entry.compress_type = zipfile.ZIP_DEFLATED

                if source_entry.is_dir():
                    output_archive.writestr(output_entry, b"")
                    continue

                with output_archive.open(
                    output_entry, "w", force_zip64=True
                ) as output_file:
                    if source_entry.filename == patched_member_name:
                        with patched_path.open("rb") as patched_file:
                            shutil.copyfileobj(patched_file, output_file)
                    else:
                        with source_archive.open(source_entry, "r") as source_file:
                            shutil.copyfileobj(source_file, output_file)
    except (
        EOFError,
        OSError,
        RuntimeError,
        NotImplementedError,
        zipfile.BadZipFile,
        zlib.error,
    ) as e:
        output_path.unlink(missing_ok=True)
        raise PatcherInputError("The patched ROM archive could not be created") from e


async def _apply_binary_patch(
    rom_path: Path, patch_path: Path, output_path: Path
) -> bool:
    """Apply ``patch_path`` to ``rom_path`` and write the result to ``output_path``.

    Returns whether the patch's embedded source checksum matched the ROM (always
    ``True`` for formats that carry no source checksum). The patch is applied
    regardless; the result lets callers warn on a likely ROM/patch mismatch.

    Raises :class:`PatcherError` if the subprocess fails, times out, or the
    output file is missing.
    """
    proc = await asyncio.create_subprocess_exec(
        "node",
        str(PATCHER_SCRIPT),
        str(rom_path),
        str(patch_path),
        str(output_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=ROM_PATCHER_TIMEOUT
        )
    except TimeoutError as e:
        proc.kill()
        await proc.wait()
        raise PatcherError(
            f"Patching timed out after {ROM_PATCHER_TIMEOUT}s"
        ) from e

    if proc.returncode != 0:
        message = "Patching failed"
        try:
            err_data = json.loads(stderr.decode())
            message = err_data.get("error", message)
        except json.JSONDecodeError, UnicodeDecodeError:
            if stderr:
                message = stderr.decode(errors="replace").strip()
        raise PatcherError(message)

    if not await AnyioPath(output_path).exists():
        raise PatcherError("Patcher did not produce an output file")

    # The script reports source-checksum validation in its JSON stdout.
    try:
        result = json.loads(stdout.decode())
        return bool(result.get("validated", True))
    except json.JSONDecodeError, UnicodeDecodeError:
        return True


async def apply_patch(
    rom_path: Path,
    patch_path: Path,
    output_path: Path,
    archive_member_name: str | None = None,
) -> bool:
    """Apply a patch to a raw ROM or to one member of a ZIP archive."""
    async with _patch_semaphore:
        extension = rom_path.suffix.lower()
        if extension != ".zip":
            if archive_member_name is not None:
                raise PatcherInputError("Archive member selection requires a ZIP ROM")
            if extension in COMPRESSED_FILE_EXTENSIONS:
                raise PatcherInputError(
                    f"ROM archives in '{extension}' format are not supported for patching"
                )
            return await _apply_binary_patch(rom_path, patch_path, output_path)

        extracted_path = output_path.parent / "source_rom"
        member_name = await asyncio.to_thread(
            _extract_zip_member, rom_path, extracted_path, archive_member_name
        )
        patched_path = output_path.parent / "patched_rom"
        validated = await _apply_binary_patch(extracted_path, patch_path, patched_path)
        patched_size = (await AnyioPath(patched_path).stat()).st_size
        if patched_size > ROM_PATCHER_MAX_FILE_SIZE_BYTES:
            raise PatcherInputError(
                "The patched ROM is too large "
                f"({patched_size} bytes, max {ROM_PATCHER_MAX_FILE_SIZE_BYTES})"
            )
        await asyncio.to_thread(
            _rebuild_zip, rom_path, output_path, patched_path, member_name
        )
        return validated
