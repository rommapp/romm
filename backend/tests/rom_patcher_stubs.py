"""A stand-in `node` for the ROM patcher tests, as CI has no RomPatcher.js."""

import os
import sys
import textwrap
from pathlib import Path

import pytest

# Mimics patcher.js: appends the patch to the ROM and reports success on stdout.
APPEND_PATCH = """
rom, patch, output = sys.argv[2:5]
data = open(rom, "rb").read() + open(patch, "rb").read()
open(output, "wb").write(data)
print(json.dumps({"success": True, "size": len(data), "validated": True}))
"""


def install_fake_node(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str
) -> None:
    """Put a `node` first on PATH that runs `body` as Python.

    Args:
        body: Python run with `json`, `os`, `sys` and `time` imported; argv is
            the script path, then the ROM, patch and output paths.
    """
    bin_dir = tmp_path / "fake-node-bin"
    bin_dir.mkdir(exist_ok=True)
    node = bin_dir / "node"
    node.write_text(
        f"#!{sys.executable}\nimport json, os, sys, time\n{textwrap.dedent(body)}"
    )
    node.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
