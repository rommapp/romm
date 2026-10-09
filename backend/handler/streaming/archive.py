"""Reading the zip archives a broker ships, and the manifest that labels their members."""

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
