"""Folding a foreign-emulator save or state pick into the one archive a
launch's `activate` call sends.

RomM never interprets a foreign asset's bytes; it only tags, wraps, and
carries them under a `.import/<kind>/<name>` member for the broker's own
declared-import contract to place. See docs/superpowers/specs/2026-09-21-
declared-save-import-romm-design.md for the wire format this builds toward.
"""

import io
import json
import time
import zipfile
from dataclasses import dataclass
from typing import Any, Literal

from handler.streaming.config import emulator_labels
from utils.zip_cache import ensure_zipfile_writable

_MANIFEST_NAME = ".broker-manifest.json"


@dataclass(frozen=True)
class ForeignMember:
    """One foreign pick's bytes, waiting to be folded into the launch's
    single `.import/` archive."""

    kind: Literal["save", "state"]
    name: str
    content: bytes
    origin: str


def origin_of(emulator: str | None, origin_device_id: str | None) -> str:
    """Where a picked save/state was captured, advisory-only per the
    broker's v2 manifest: "hardware" when a device tagged it, "unknown" for
    an untagged manual upload, "standalone" when its `emulator` names one of
    the streaming subsystem's own containers, else "emulatorjs" (EmulatorJS
    writes its active core's name into the same field)."""
    if origin_device_id is not None:
        return "hardware"
    if not emulator:
        return "unknown"
    return "standalone" if emulator.lower() in emulator_labels() else "emulatorjs"


def _safe_name(name: str) -> str | None:
    """None when this zip member is junk that must never ride in an import
    archive (a dotfile, or macOS's resource-fork sidecar folder)."""
    normalized = name.replace("\\", "/")
    parts = [p for p in normalized.split("/") if p]
    if not parts or parts[0] == "__MACOSX" or any(p.startswith(".") for p in parts):
        return None
    return "/".join(parts)


def _utf8_zipinfo(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=time.localtime()[:6])
    info.flag_bits |= 0x800  # UTF-8 filename flag
    info.compress_type = zipfile.ZIP_DEFLATED
    return info


def _read_base_manifest(base_zf: zipfile.ZipFile) -> dict[str, Any] | None:
    if _MANIFEST_NAME not in base_zf.namelist():
        return None
    try:
        return json.loads(base_zf.read(_MANIFEST_NAME))
    except (json.JSONDecodeError, KeyError):
        return None


def _write_member(
    zf: zipfile.ZipFile, member: ForeignMember, carried: list[dict[str, Any]]
) -> None:
    if zipfile.is_zipfile(io.BytesIO(member.content)):
        with zipfile.ZipFile(io.BytesIO(member.content)) as inner:
            for info in inner.infolist():
                if info.is_dir():
                    continue
                name = _safe_name(info.filename)
                if name is None:
                    continue
                path = f".import/{member.kind}/{name}"
                zf.writestr(_utf8_zipinfo(path), inner.read(info.filename))
                carried.append(
                    {"path": path, "kind": member.kind, "origin": member.origin}
                )
        return
    name = _safe_name(member.name) or "data"
    path = f".import/{member.kind}/{name}"
    zf.writestr(_utf8_zipinfo(path), member.content)
    carried.append({"path": path, "kind": member.kind, "origin": member.origin})


def build_import_archive(
    rom_id: int,
    base: tuple[str, bytes] | None,
    members: list[ForeignMember],
) -> bytes:
    """Build the single zip `activate`'s `save.archive` wants.

    Carries over the base archive's own members verbatim (its old
    `.broker-manifest.json` is dropped and rewritten as v2), except its v1
    state member, which is stripped whenever a foreign state is among
    `members` since the import replaces it. Adds one `.import/<kind>/<name>`
    member per foreign member (its own inner members, when its content is
    itself a zip). Drops dotfiles and `__MACOSX` entries and forces UTF-8
    names on every member copied in, base or foreign.
    """
    ensure_zipfile_writable()
    strip_state = any(m.kind == "state" for m in members)
    carried: list[dict[str, Any]] = []
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        if base is not None:
            _, base_content = base
            with zipfile.ZipFile(io.BytesIO(base_content)) as base_zf:
                base_manifest = _read_base_manifest(base_zf)
                base_files = {
                    f["path"]: f
                    for f in (base_manifest or {}).get("files", [])
                    if isinstance(f, dict) and isinstance(f.get("path"), str)
                }
                for info in base_zf.infolist():
                    if info.is_dir() or info.filename == _MANIFEST_NAME:
                        continue
                    name = _safe_name(info.filename)
                    if name is None:
                        continue
                    entry = base_files.get(info.filename) or base_files.get(name)
                    if (
                        strip_state
                        and entry is not None
                        and entry.get("kind") == "state"
                    ):
                        continue
                    zf.writestr(_utf8_zipinfo(name), base_zf.read(info.filename))
                    carried.append(
                        entry if entry is not None else {"path": name, "kind": "save"}
                    )
        for member in members:
            _write_member(zf, member, carried)
        zf.writestr(
            _MANIFEST_NAME,
            json.dumps(
                {
                    "version": 2,
                    "created_at": time.time(),
                    "import": {"source": "romm", "rom_id": rom_id},
                    "files": carried,
                }
            ),
        )
    return out.getvalue()
