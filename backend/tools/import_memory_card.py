#!/usr/bin/env python3
"""Import a Slot-1 folder memory-card zip as a user's MemoryCard version.

One-shot seed for migrating a card that already lives inside an emulator
container into the per-user whole-card model. Grab the card first with an
authenticated GET against the broker:

    curl -H "X-Broker-Secret: <secret>" \
        http://<broker-host>:8000/memory-card -o pcsx2-card.zip

Then, from the backend directory on the RomM instance:

    uv run python -m tools.import_memory_card zclendenen pcsx2 pcsx2-card.zip

Reuses the user's most-recent card for the emulator if one exists, otherwise
creates a blank card and stores the zip as its version 1. Dedupes by content
hash, so re-running with an identical card does nothing.
"""

import asyncio
import io
import sys
import zipfile

# isort: off
# Load the auth package first so the decorators.auth <-> handler.auth import
# cycle resolves before endpoints.streaming pulls it in (matches the module
# order the app's own entrypoint establishes at startup). Keep isort from
# reordering these below the endpoints import.
import handler.auth  # noqa: F401,E402
from endpoints.streaming import _store_memory_card_version  # noqa: E402

# isort: on
from handler.database import db_memory_card_handler, db_user_handler
from models.assets import MemoryCard


async def _import(username: str, emulator: str, content: bytes) -> int:
    user = db_user_handler.get_user_by_username(username)
    if user is None:
        print(f"error: no user named {username!r}", file=sys.stderr)
        return 2

    cards = db_memory_card_handler.get_cards(user.id, emulator)
    if cards:
        card = cards[0]  # most-recently-updated
        print(f"reusing card id={card.id} name={card.name!r}")
    else:
        card = db_memory_card_handler.add_card(
            MemoryCard(
                user_id=user.id,
                emulator=emulator,
                platform_id=None,
                name=f"{emulator} memory card",
                slot=1,
                is_public=False,
            )
        )
        print(f"created blank card id={card.id}")

    stored = await _store_memory_card_version(user, card, emulator, content)
    latest = db_memory_card_handler.get_latest_version(card.id)
    print(
        f"stored={stored} card_id={card.id} "
        f"latest_version={latest.file_name if latest else None} "
        f"hash={latest.content_hash if latest else None}"
    )
    return 0


def main() -> int:
    if len(sys.argv) != 4:
        print(
            "usage: python -m tools.import_memory_card <username> <emulator> <zip>",
            file=sys.stderr,
        )
        return 2
    _, username, emulator, zip_path = sys.argv

    with open(zip_path, "rb") as fh:
        content = fh.read()
    if not content:
        print(f"error: {zip_path} is empty", file=sys.stderr)
        return 2
    # Guard against importing a non-archive: a `curl -o` of a broker 404/409
    # writes the JSON error body to the file, which must never become a card.
    if not zipfile.is_zipfile(io.BytesIO(content)):
        print(
            f"error: {zip_path} is not a zip archive "
            f"(got {content[:80]!r}); did the broker GET return an error body?",
            file=sys.stderr,
        )
        return 2

    return asyncio.run(_import(username, emulator, content))


if __name__ == "__main__":
    raise SystemExit(main())
