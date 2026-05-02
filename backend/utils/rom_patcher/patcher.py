"""Server-side ROM patching helpers.

Shells out to the sibling ``patcher.js`` (Node.js + RomPatcher.js) to apply
a patch file to a ROM file.
"""

import asyncio
import json
from pathlib import Path

PATCHER_SCRIPT = Path(__file__).parent / "patcher.js"

SUPPORTED_PATCH_EXTENSIONS = frozenset(
    (".ips", ".ups", ".bps", ".ppf", ".rup", ".aps", ".bdf", ".pmsr", ".vcdiff")
)


class PatcherError(Exception):
    """Raised when the Node.js patcher script fails or produces no output."""


async def apply_patch(rom_path: Path, patch_path: Path, output_path: Path) -> None:
    """Apply ``patch_path`` to ``rom_path`` and write the result to ``output_path``.

    Raises :class:`PatcherError` if the subprocess exits non-zero or the output
    file is missing.
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
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        message = "Patching failed"
        try:
            err_data = json.loads(stderr.decode())
            message = err_data.get("error", message)
        except (json.JSONDecodeError, UnicodeDecodeError):
            if stderr:
                message = stderr.decode(errors="replace").strip()
        raise PatcherError(message)

    if not output_path.exists():
        raise PatcherError("Patcher did not produce an output file")
