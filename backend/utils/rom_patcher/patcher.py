"""Server-side ROM patching helpers.

Shells out to the sibling ``patcher.js`` (Node.js + RomPatcher.js) to apply
a patch file to a ROM file.
"""

import asyncio
import json
from pathlib import Path

from anyio import Path as AnyioPath

from config import ROM_PATCHER_MAX_CONCURRENCY, ROM_PATCHER_TIMEOUT

PATCHER_SCRIPT = Path(__file__).parent / "patcher.js"

SUPPORTED_PATCH_EXTENSIONS = frozenset(
    (".ips", ".ups", ".bps", ".ppf", ".rup", ".aps", ".bdf", ".pmsr", ".vcdiff")
)

# Bound concurrent node subprocesses, each of which loads a full ROM into memory.
_patch_semaphore = asyncio.Semaphore(ROM_PATCHER_MAX_CONCURRENCY)


class PatcherError(Exception):
    """Raised when the Node.js patcher script fails or produces no output."""


async def apply_patch(rom_path: Path, patch_path: Path, output_path: Path) -> bool:
    """Apply ``patch_path`` to ``rom_path`` and write the result to ``output_path``.

    Returns whether the patch's embedded source checksum matched the ROM (always
    ``True`` for formats that carry no source checksum). The patch is applied
    regardless; the result lets callers warn on a likely ROM/patch mismatch.

    Raises :class:`PatcherError` if the subprocess fails, times out, or the
    output file is missing.
    """
    async with _patch_semaphore:
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
        except (asyncio.TimeoutError, TimeoutError) as e:
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
        except (json.JSONDecodeError, UnicodeDecodeError):
            if stderr:
                message = stderr.decode(errors="replace").strip()
        raise PatcherError(message)

    if not await AnyioPath(output_path).exists():
        raise PatcherError("Patcher did not produce an output file")

    # The script reports source-checksum validation in its JSON stdout.
    try:
        result = json.loads(stdout.decode())
        return bool(result.get("validated", True))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return True
