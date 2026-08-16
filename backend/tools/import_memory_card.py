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

from handler.database import db_memory_card_handler, db_user_handler
from models.assets import MemoryCard
from utils.memory_cards import (
    MEMORY_CARD_MAX_BYTES,
    UnsafeCardArchive,
    assert_card_archive_safe,
    store_memory_card_version,
)


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

    version = await store_memory_card_version(user, card, content)
    print(
        f"stored={version is not None} card_id={card.id} "
        f"version={version.file_name if version else None} "
        f"hash={version.content_hash if version else None}"
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
        content = fh.read(MEMORY_CARD_MAX_BYTES + 1)
    if not content:
        print(f"error: {zip_path} is empty", file=sys.stderr)
        return 2
    # The upload route enforces the same ceiling, and the broker refuses
    # anything larger; importing past it just moves where the transfer fails.
    if len(content) > MEMORY_CARD_MAX_BYTES:
        print(
            f"error: {zip_path} exceeds the {MEMORY_CARD_MAX_BYTES} byte card limit",
            file=sys.stderr,
        )
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
    # The same gate the upload route applies: a card imported here hydrates onto
    # a container exactly like an uploaded one.
    try:
        assert_card_archive_safe(content)
    except UnsafeCardArchive as exc:
        print(f"error: {zip_path} rejected, {exc}", file=sys.stderr)
        return 2

    return asyncio.run(_import(username, emulator, content))


if __name__ == "__main__":
    raise SystemExit(main())
