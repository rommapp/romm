"""Button catalog for the install auto mode.

Loaded from ``buttons.yml`` plus optional user entries from config.yml
(``install.auto_mode_extra_buttons``), so supporting a new installer is a
data change, not a code change.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

CATALOG_PATH = Path(__file__).with_name("buttons.yml")

CATEGORIES = ("next", "agree", "install", "finish", "key", "deny")

_PAREN_RE = re.compile(r"[\(（][^\)）]*[\)）]")
_NON_WORD_RE = re.compile(r"[\W_]+", re.UNICODE)


def normalize(text: str) -> str:
    """Case-fold and drop everything OCR and installers add around a label:
    spaces, ``&``/``>`` markers, punctuation and a trailing ``(N)`` mnemonic."""
    # OCR reads a capital "I" as a pipe.
    return _NON_WORD_RE.sub("", _PAREN_RE.sub("", text).casefold().replace("|", "i"))


@dataclass(frozen=True, slots=True)
class ButtonEntry:
    category: str
    labels: tuple[str, ...]
    mnemonic: str | None = None
    toggle: bool = False
    # ``key`` entries: xdotool key name pressed when the label is on screen.
    key: str | None = None
    # Only used once the install has written files (e.g. "Exit" must never be
    # pressed on a start screen).
    late: bool = False

    @property
    def normalized_labels(self) -> tuple[str, ...]:
        return tuple(n for n in (normalize(x) for x in self.labels) if n)


@dataclass(frozen=True, slots=True)
class Catalog:
    buttons: tuple[ButtonEntry, ...]
    license_keywords: tuple[str, ...]
    confirm_keywords: tuple[str, ...]

    def entries(self, category: str) -> tuple[ButtonEntry, ...]:
        return tuple(b for b in self.buttons if b.category == category)


def _parse_entry(raw: dict) -> ButtonEntry | None:
    category = raw.get("category")
    labels = raw.get("labels")
    if category not in CATEGORIES or not isinstance(labels, list):
        return None
    mnemonic = raw.get("mnemonic")
    if category == "key" and not raw.get("key"):
        return None
    return ButtonEntry(
        category=category,
        labels=tuple(str(x) for x in labels if str(x).strip()),
        mnemonic=str(mnemonic).lower()[:1] if mnemonic else None,
        toggle=bool(raw.get("toggle", False)) and category == "agree",
        key=str(raw["key"]) if category == "key" and raw.get("key") else None,
        late=bool(raw.get("late", False)),
    )


def _keywords(context: dict, key: str) -> tuple[str, ...]:
    return tuple(k for k in (normalize(x) for x in context.get(key, [])) if k)


def load_catalog(extra_buttons: list[dict] | None = None) -> Catalog:
    raw = yaml.safe_load(CATALOG_PATH.read_text(encoding="utf-8")) or {}
    entries = [_parse_entry(x) for x in raw.get("buttons", [])]
    entries += [_parse_entry(x) for x in extra_buttons or [] if isinstance(x, dict)]
    context = raw.get("context_keywords", {})
    return Catalog(
        buttons=tuple(e for e in entries if e is not None),
        license_keywords=_keywords(context, "license"),
        confirm_keywords=_keywords(context, "confirm"),
    )
