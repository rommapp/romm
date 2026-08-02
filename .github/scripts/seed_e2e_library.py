"""Scan the library at ROMM_BASE_PATH with no metadata providers.

The e2e suite needs at least one ROM to open a details page against. This runs
the same `scan_platforms` the scan socket enqueues, but with an empty
`metadata_sources` list so it never reaches out to IGDB/MobyGames/etc -- keeping
it hermetic and fast enough for CI.

    ROMM_BASE_PATH=/path/with/library uv run python .github/scripts/seed_e2e_library.py

Exits non-zero if the scan produced no ROMs, so CI fails on a missing or empty
library fixture instead of later, as a confusing Playwright timeout.
"""

from __future__ import annotations

import asyncio
import os
import sys

# Add /backend to the path so these can import `handler.*` / `models.*`.
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
)

from endpoints.sockets.scan import scan_platforms  # noqa: E402
from handler.scan_handler import ScanType  # noqa: E402


async def _scan() -> int:
    stats = await scan_platforms(
        platform_ids=[],
        metadata_sources=[],
        scan_type=ScanType.QUICK,
    )
    print(
        f"scanned platforms={stats.scanned_platforms} roms={stats.scanned_roms} "
        f"(new platforms={stats.new_platforms}, new roms={stats.new_roms})"
    )
    if stats.scanned_roms == 0:
        print(
            "No ROMs scanned -- is ROMM_BASE_PATH pointing at a library fixture?",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_scan()))
