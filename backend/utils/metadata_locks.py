from __future__ import annotations

from typing import Any, Literal, TypeAlias, get_args

from models.rom import Rom

MetadataLockField: TypeAlias = Literal[
    "name",
    "summary",
    "cover",
    "screenshots",
    "manual",
    "genres",
    "franchises",
    "collections",
    "companies",
    "game_modes",
    "age_ratings",
    "first_release_date",
    "player_count",
]
METADATA_LOCKABLE_FIELDS = frozenset(get_args(MetadataLockField))
PROJECTED_METADATA_LOCK_FIELDS = METADATA_LOCKABLE_FIELDS - {
    "name",
    "summary",
    "cover",
    "screenshots",
    "manual",
}


def effective_metadata_value(rom: Rom, field: str) -> Any:
    """Read a lockable field as the user currently sees it."""
    if field in PROJECTED_METADATA_LOCK_FIELDS:
        return getattr(rom.metadatum, field)
    if field == "cover":
        return {
            "url": rom.url_cover,
            "small": rom.path_cover_s,
            "large": rom.path_cover_l,
        }
    if field == "screenshots":
        return {
            "urls": rom.url_screenshots or [],
            "paths": rom.path_screenshots or [],
        }
    if field == "manual":
        return {"url": rom.url_manual, "path": rom.path_manual}
    return getattr(rom, field)


def apply_metadata_lock_snapshots(
    rom_attrs: dict[str, Any], locks: dict[str, Any] | None
) -> None:
    """Apply direct and asset snapshots to scanner-owned attributes."""
    for field, snapshot in (locks or {}).items():
        if field in {"name", "summary"}:
            rom_attrs[field] = snapshot
        elif field == "cover":
            rom_attrs.update(
                url_cover=snapshot["url"],
                path_cover_s=snapshot["small"],
                path_cover_l=snapshot["large"],
            )
        elif field == "screenshots":
            rom_attrs.update(
                url_screenshots=snapshot["urls"],
                path_screenshots=snapshot["paths"],
            )
        elif field == "manual":
            rom_attrs.update(url_manual=snapshot["url"], path_manual=snapshot["path"])
