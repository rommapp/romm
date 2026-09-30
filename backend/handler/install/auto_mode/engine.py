"""Decide what to press on the current screen. Pure logic, no X11 or OCR."""

from __future__ import annotations

from dataclasses import dataclass, field

from .catalog import Catalog
from .matcher import Match, Word, find_matches, screen_lines

# Two OCR line sets at least this similar (Jaccard) are the same installer page.
SAME_SCREEN_THRESHOLD = 0.7
MAX_ATTEMPTS_PER_BUTTON = 2

# Lower is pressed first. Agree entries are only ever used on license pages.
_PRIORITY = {
    "key": -1,
    "toggle": 0,
    "install": 1,
    "finish": 2,
    "next": 3,
    "agree": 4,
    "option": 4,
}


@dataclass(frozen=True, slots=True)
class Action:
    kind: str  # "click" | "key"
    x: int
    y: int
    key: str | None
    match: Match
    memory_key: str
    alt: bool = True

    def describe(self) -> str:
        if self.kind == "key":
            target = f"Alt+{self.key}" if self.alt else f"key {self.key}"
        else:
            target = "click"
        return f"{target} on '{self.match.text}' ({self.match.entry.category})"


@dataclass
class ScreenMemory:
    lines: frozenset[str] = frozenset()
    attempts: dict[str, int] = field(default_factory=dict)


def similarity(a: frozenset[str], b: frozenset[str]) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def same_screen(a: frozenset[str], b: frozenset[str]) -> bool:
    return similarity(a, b) >= SAME_SCREEN_THRESHOLD


def is_license_page(lines: list[str], catalog: Catalog) -> bool:
    return any(k in line for line in lines for k in catalog.license_keywords)


def is_confirm_page(lines: list[str], catalog: Catalog) -> bool:
    """A plain Yes/No prerequisite prompt ("Do you want to install
    DirectX?"), not a EULA, but just as safe to answer Yes to - see
    buttons.yml's own "confirm" keyword list."""
    return any(k in line for line in lines for k in catalog.confirm_keywords)


def _priority(match: Match) -> int:
    entry = match.entry
    return _PRIORITY["toggle" if entry.toggle else entry.category]


def plan_action(
    words: list[Word],
    catalog: Catalog,
    memory: ScreenMemory,
    installing: bool = False,
) -> tuple[Action | None, list[Match]]:
    """Return the next thing to try (or None) and every match on screen.

    Each button gets a click first and, when that changed nothing, its
    Alt+mnemonic. A button that exhausted its attempts is skipped so the
    next candidate gets a turn.
    """
    lines = screen_lines(words)
    matches = find_matches(words, catalog)
    license_page = is_license_page(lines, catalog)
    agree_allowed = license_page or is_confirm_page(lines, catalog)

    ranked: list[tuple[tuple[int, int], Match, str, int]] = []
    for m in matches:
        if m.entry.category == "agree" and not agree_allowed:
            continue
        if m.entry.late and not installing:
            continue
        key = f"{m.entry.category}:{m.label}"
        attempts = memory.attempts.get(key, 0)
        if attempts >= MAX_ATTEMPTS_PER_BUTTON:
            continue
        # A repeated checkbox click would undo the first, so a toggle only
        # gets its retry after every other button had its turn.
        penalty = 1 if m.entry.toggle and attempts >= 1 else 0
        ranked.append(((penalty, _priority(m)), m, key, attempts))
    if not ranked:
        return None, matches

    _, match, key, attempts = min(ranked, key=lambda r: r[0])
    if match.entry.category == "key":
        return (
            Action("key", 0, 0, match.entry.key, match, key, alt=match.entry.key_alt),
            matches,
        )
    if attempts >= 1 and match.entry.mnemonic:
        return Action("key", 0, 0, match.entry.mnemonic, match, key), matches
    x, y = match.center
    if attempts >= 1 and match.entry.toggle:
        # Retry on the radio/checkbox glyph itself, left of its label.
        x = match.left - max(match.height, 8)
    return Action("click", x, y, None, match, key), matches
