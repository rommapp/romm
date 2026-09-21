import csv
import io
from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Final

from models.rom import RomUser, RomUserStatus

# Backloggd has no native CSV import; these are the columns the community
# importers read, so the file is only as stable as they are.
CSV_HEADER: Final = ["Game", "Year Released", "Rating", "Status", "Date Played"]

# A Backloggd log carries one status where RomM spreads the same information
# over three fields. What is absent here has no counterpart and exports blank.
_STATUS_BY_ROM_USER_STATUS: Final[dict[RomUserStatus, str]] = {
    RomUserStatus.FINISHED: "completed",
    RomUserStatus.COMPLETED_100: "completed",
    RomUserStatus.INCOMPLETE: "playing",
}

_STATUS_RANK: Final[dict[str, int]] = {
    "": 0,
    "backlog": 1,
    "playing": 2,
    "completed": 3,
}

# A spreadsheet evaluates a cell opening with one of these, and a game name
# reaches the file from provider metadata or the filename on disk.
_FORMULA_PREFIXES: Final = ("=", "+", "-", "@")


def _status(rom_user: RomUser) -> str:
    # The flags are independent of `status`, so an explicit `retired` has to
    # stop here rather than fall through to a stale `now_playing`.
    if rom_user.status:
        return _STATUS_BY_ROM_USER_STATUS.get(rom_user.status, "")
    if rom_user.now_playing:
        return "playing"
    if rom_user.backlogged:
        return "backlog"
    return ""


def _rating(rating: int) -> str:
    """RomM's 1-10 is Backloggd's 0.5-5.0 half-star scale, step for step."""
    return f"{rating / 2:.1f}" if rating else ""


def _release_year(timestamp_ms: int | None) -> str:
    # Provider blobs feed this column, so an out-of-range value is possible.
    if not timestamp_ms:
        return ""
    try:
        return str(datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC).year)
    except OverflowError, OSError, ValueError:
        return ""


def _date_played(last_played: datetime | None) -> str:
    if not last_played:
        return ""
    if last_played.tzinfo is None:
        last_played = last_played.replace(tzinfo=UTC)
    return last_played.astimezone(UTC).strftime("%Y-%m-%d")


def _game_name(rom_user: RomUser) -> str:
    return (rom_user.rom.name or rom_user.rom.fs_name or "").strip()


def _formula_safe(name: str) -> str:
    """Prefix a name a spreadsheet would evaluate as a formula, keeping it text."""
    return f"'{name}" if name.startswith(_FORMULA_PREFIXES) else name


def _group_key(rom_user: RomUser) -> tuple[str, str | int]:
    """One log per game: siblings are separate ROMs but the same Backloggd entry."""
    rom = rom_user.rom
    if rom.igdb_id:
        return ("igdb", rom.igdb_id)
    return ("name", _game_name(rom_user).casefold())


def _row(group: list[RomUser]) -> list[str]:
    """Fold sibling ROMs into the one log Backloggd would hold for the game."""
    # Each field takes the group's best value rather than picking a winning row,
    # by a rule that is order-independent: siblings arrive in no set order.
    years = [_release_year(ru.rom.generated_first_release_date) for ru in group]
    dates = [_date_played(ru.last_played) for ru in group]
    return [
        _formula_safe(min(_game_name(ru) for ru in group)),
        min((year for year in years if year), default=""),
        _rating(max((ru.rating for ru in group if ru.rating), default=0)),
        max((_status(ru) for ru in group), key=lambda status: _STATUS_RANK[status]),
        max((date for date in dates if date), default=""),
    ]


def build_csv(rom_users: Iterable[RomUser]) -> str:
    """Render a user's play state as a Backloggd-importable CSV."""
    groups: dict[tuple[str, str | int], list[RomUser]] = defaultdict(list)
    for rom_user in rom_users:
        if _game_name(rom_user):
            groups[_group_key(rom_user)].append(rom_user)

    rows = [_row(group) for group in groups.values()]
    rows.sort(key=lambda row: row[0].casefold())

    buffer = io.StringIO()
    writer = csv.writer(buffer, quoting=csv.QUOTE_MINIMAL)
    writer.writerow(CSV_HEADER)
    writer.writerows(rows)
    return buffer.getvalue()
