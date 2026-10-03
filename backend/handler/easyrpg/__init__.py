"""Serves RPG Maker 2000/2003 game folders, with the free RTP merged in, to the EasyRPG web player."""

import json
import os
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from functools import cached_property
from pathlib import Path
from typing import Any, Final

from models.rom import EASYRPG_GAME_DATABASE, RomFile

# The image ships the free RTP beside the web player, which nginx serves.
RTP_WEB_PATH: Final = "/assets/easyrpg/rtp"
RTP_PATH: Final = f"/var/www/html{RTP_WEB_PATH}"

INDEX_FILE: Final = "index.json"
# gencache keeps these extensions on files below the game root.
_KEPT_EXTENSIONS: Final = (".ini", ".po")
_DIRNAME_KEY: Final = "_dirname"
_RTP_TABLE_PATH: Final = Path(__file__).with_name("rtp_table.json")

type RtpTable = Mapping[str, Sequence[Sequence[str]]]


def normalize_name(name: str) -> str:
    """The key the player looks a file up by, as gencache derives it."""
    return unicodedata.normalize("NFKC", name.lower())


def _strip_extension(name: str) -> str:
    dot = name.rfind(".")
    return name[:dot] if dot != -1 else name


def _file_key(name: str, at_root: bool) -> str:
    key = normalize_name(name)
    if at_root or key.endswith(_KEPT_EXTENSIONS):
        return "exfont" if _strip_extension(key) == "exfont" else key
    return _strip_extension(key)


def _rtp_aliases(rtp_table: RtpTable, category: str) -> dict[str, set[str]]:
    """Every name an RTP asset of `category` goes by, keyed by each of them."""
    aliases: dict[str, set[str]] = {}
    for row in rtp_table.get(category, []):
        for name in row:
            aliases.setdefault(name, set()).update(row)
    return aliases


def build_index(
    game_files: Iterable[str],
    rtp_files: Mapping[str, Sequence[str]],
    rtp_table: RtpTable,
) -> dict[str, Any]:
    """Build a version 2 `index.json` for a game, the format gencache writes.

    Args:
        game_files: Paths of the game's files, relative to its folder.
        rtp_files: RTP file names, keyed by their folder.
        rtp_table: Names of each RTP asset, keyed by category.
    """
    cache: dict[str, Any] = {}
    for path in game_files:
        *dirs, name = path.split("/")
        node: Any = cache
        for dir_name in dirs:
            node = node.setdefault(normalize_name(dir_name), {_DIRNAME_KEY: dir_name})
            if not isinstance(node, dict):
                break
        else:
            if name != _DIRNAME_KEY:
                node.setdefault(_file_key(name, at_root=not dirs), name)

    # The game's own files win over the RTP's.
    for dir_name, names in sorted(rtp_files.items()):
        category = normalize_name(dir_name)
        node = cache.setdefault(category, {_DIRNAME_KEY: dir_name})
        if not isinstance(node, dict):
            continue
        aliases = _rtp_aliases(rtp_table, category)
        for name in sorted(names):
            stem = normalize_name(_strip_extension(name))
            for alias in sorted(aliases.get(stem, {stem})):
                node.setdefault(alias, name)

    return {"metadata": {"version": 2}, "cache": cache}


class EasyRpgHandler:
    def __init__(self, rtp_path: str = RTP_PATH) -> None:
        self.rtp_path = rtp_path

    @cached_property
    def rtp_table(self) -> RtpTable:
        table: RtpTable = json.loads(_RTP_TABLE_PATH.read_text(encoding="utf-8"))
        return table

    @cached_property
    def rtp_files(self) -> dict[str, list[str]]:
        """The RTP's files by folder, or nothing when the image has no RTP."""
        try:
            folders = os.scandir(self.rtp_path)
        except OSError:
            return {}
        with folders:
            return {
                folder.name: sorted(
                    entry.name
                    for entry in os.scandir(folder.path)
                    if entry.is_file() and not entry.name.startswith(".")
                )
                for folder in folders
                if folder.is_dir() and not folder.name.startswith(".")
            }

    @cached_property
    def _rtp_folders(self) -> dict[str, tuple[str, frozenset[str]]]:
        """Each RTP folder and its file names, keyed by the normalized folder name."""
        return {
            normalize_name(folder): (folder, frozenset(names))
            for folder, names in self.rtp_files.items()
        }

    @staticmethod
    def game_files(files: Iterable[RomFile]) -> dict[str, RomFile]:
        """A game's files, keyed by their path inside its folder."""
        return {file.file_name_for_download(): file for file in files}

    @staticmethod
    def is_game(game_files: Iterable[str]) -> bool:
        return any(normalize_name(path) == EASYRPG_GAME_DATABASE for path in game_files)

    def build_index(self, game_files: Iterable[str]) -> dict[str, Any]:
        return build_index(game_files, self.rtp_files, self.rtp_table)

    def find_rtp_file(self, path: str) -> str | None:
        """The RTP file `path` names, under whatever folder spelling the index gave it.

        Returns:
            The file's path inside the RTP, or None when the RTP has no such file.
        """
        dir_name, _, name = path.rpartition("/")
        folder, names = self._rtp_folders.get(
            normalize_name(dir_name), ("", frozenset())
        )
        return f"{folder}/{name}" if name in names else None


easyrpg_handler = EasyRpgHandler()
