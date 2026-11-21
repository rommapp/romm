"""Reading the zip archives a broker ships, and the manifest that labels their members."""

import io
import json
import zipfile
from typing import Any

MANIFEST_NAME = ".broker-manifest.json"
MAX_MANIFEST_BYTES = 1024 * 1024
_READ_CHUNK = 64 * 1024


def read_member(zf: zipfile.ZipFile, info: zipfile.ZipInfo) -> bytes:
    """An entry's bytes, inflated a chunk at a time so a size the header
    understates fails the CRC check before it can exhaust memory."""
    out = bytearray()
    with zf.open(info) as f:
        while chunk := f.read(_READ_CHUNK):
            out += chunk
    return bytes(out)


def read_manifest(zf: zipfile.ZipFile) -> dict[str, Any]:
    """A broker archive's manifest, empty when it has none or it doesn't parse."""
    try:
        info = zf.getinfo(MANIFEST_NAME)
    except KeyError:
        return {}
    if info.file_size > MAX_MANIFEST_BYTES:
        raise ValueError("broker manifest exceeds its size limit")
    try:
        manifest = json.loads(read_member(zf, info))
    except json.JSONDecodeError, UnicodeDecodeError:
        return {}
    return manifest if isinstance(manifest, dict) else {}


def manifest_files(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """A manifest's `files` entries by path."""
    files = manifest.get("files")
    return {
        f["path"]: f
        for f in (files if isinstance(files, list) else [])
        if isinstance(f, dict) and isinstance(f.get("path"), str)
    }


def overlay(base: bytes, top: bytes, max_bytes: int) -> bytes:
    """`base` with `top`'s members written over it, under one merged manifest.

    Raises:
        zipfile.BadZipFile: either side is not a zip.
        ValueError: the merged members would expand past `max_bytes`.
    """
    members: dict[str, tuple[zipfile.ZipInfo, bytes]] = {}
    labels: dict[str, dict[str, Any]] = {}
    manifest: dict[str, Any] = {}
    expanded = 0
    for content in (base, top):
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            own = read_manifest(zf)
            manifest = own or manifest
            own_labels = manifest_files(own)
            for info in zf.infolist():
                if info.is_dir() or info.filename == MANIFEST_NAME:
                    continue
                replaced = members.pop(info.filename, None)
                if replaced is not None:
                    expanded -= replaced[0].file_size
                expanded += info.file_size
                if expanded > max_bytes:
                    raise ValueError("merged archive exceeds its size limit")
                members[info.filename] = (info, read_member(zf, info))
                # A label travels with its own archive's bytes, unlabelled ones
                # as a save, as an import archive labels its base.
                labels[info.filename] = own_labels.get(
                    info.filename, {"path": info.filename, "kind": "save"}
                )

    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, (info, data) in members.items():
            entry = zipfile.ZipInfo(name, date_time=info.date_time)
            # The mode bits only mean what they say under the system that wrote them.
            entry.create_system = info.create_system
            entry.external_attr = info.external_attr
            entry.flag_bits |= info.flag_bits & 0x800  # UTF-8 filename flag
            entry.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(entry, data)
        if manifest:
            files = [labels[name] for name in members]
            zf.writestr(MANIFEST_NAME, json.dumps({**manifest, "files": files}))
    return out.getvalue()
