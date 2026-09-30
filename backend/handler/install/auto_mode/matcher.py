"""Turn OCR words into pressable button candidates."""

from __future__ import annotations

from dataclasses import dataclass

from .catalog import ButtonEntry, Catalog, normalize

# Longest label (in OCR words) worth trying to assemble.
MAX_SPAN_WORDS = 14
# Toggle labels (radio/checkbox sentences) at least this long may match
# inside a longer OCR line, since the control glyph is often read as a
# stray character in front of the text.
LONG_LABEL_LEN = 8
# Labels this long tolerate one OCR typo. Every button label must be the
# whole line or stand alone, or "Si"/"OK" would match ordinary body text.
FUZZY_LABEL_LEN = 5
# A short label counts as standing alone when the gap to its neighbours on
# the same OCR line exceeds this many times the text height.
ISOLATION_GAP_FACTOR = 2.0
MIN_WORD_CONF = 30
# Button and checkbox labels are UI-font sized; a taller match is a page
# title ("Installation") or artwork text, and clicking it does nothing.
MAX_LABEL_HEIGHT = 30
# A real button never appears this many times on one screen. A short,
# generic label ("OK") repeated past this is a status column in a data
# table (a file-verification tool's per-row "OK", not a button) - see
# find_matches's own filtering.
MAX_PLAUSIBLE_REPEATS = 3


@dataclass(frozen=True, slots=True)
class Word:
    text: str
    left: int
    top: int
    width: int
    height: int
    conf: float = 100.0
    line_id: tuple[int, int, int] = (0, 0, 0)

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height


@dataclass(frozen=True, slots=True)
class Match:
    entry: ButtonEntry
    label: str
    text: str
    left: int
    top: int
    width: int
    height: int

    @property
    def center(self) -> tuple[int, int]:
        return self.left + self.width // 2, self.top + self.height // 2


def _edit_distance_at_most_one(a: str, b: str) -> bool:
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) > len(b):
        a, b = b, a
    i = j = edits = 0
    while i < len(a) and j < len(b):
        if a[i] == b[j]:
            i += 1
            j += 1
            continue
        edits += 1
        if edits > 1:
            return False
        if len(a) == len(b):
            i += 1
        j += 1
    return edits + (len(b) - j) + (len(a) - i) <= 1


def _group_lines(words: list[Word]) -> list[list[Word]]:
    lines: dict[tuple[int, int, int], list[Word]] = {}
    for w in words:
        if w.conf >= MIN_WORD_CONF and normalize(w.text):
            lines.setdefault(w.line_id, []).append(w)
    grouped = []
    for ws in lines.values():
        ws = sorted(ws, key=lambda w: w.left)
        # The border of a button is read as "|" or "[": symbols at the ends of
        # a line are frame, not text (a "|" inside a line is an "I").
        while len(ws) > 1 and not any(c.isalnum() for c in ws[0].text):
            ws.pop(0)
        while len(ws) > 1 and not any(c.isalnum() for c in ws[-1].text):
            ws.pop()
        grouped.append(ws)
    return grouped


def screen_lines(words: list[Word]) -> list[str]:
    """Normalized text of every OCR line, for screen signatures and keywords."""
    return [
        n
        for n in (normalize("".join(w.text for w in ws)) for ws in _group_lines(words))
        if n
    ]


def _is_isolated(line: list[Word], start: int, end: int) -> bool:
    if start == 0 and end == len(line):
        return True
    height = max(w.height for w in line[start:end])
    limit = ISOLATION_GAP_FACTOR * height
    if start > 0 and line[start].left - line[start - 1].right <= limit:
        return False
    if end < len(line) and line[end].left - line[end - 1].right <= limit:
        return False
    return True


def _label_matches(
    candidate: str,
    label: str,
    whole_line: bool,
    isolated: bool,
    fuzzy: bool = True,
) -> bool:
    if candidate == label:
        return whole_line or isolated
    if fuzzy and len(label) >= FUZZY_LABEL_LEN and (whole_line or isolated):
        return _edit_distance_at_most_one(candidate, label)
    return False


def find_matches(words: list[Word], catalog: Catalog) -> list[Match]:
    """Every catalog label found on screen, deny-listed lines excluded."""
    # Short deny labels ("Back") would swallow neighbouring buttons that OCR
    # put on the same line, and they never match a button label anyway.
    deny = [
        lbl
        for entry in catalog.entries("deny")
        for lbl in entry.normalized_labels
        if len(lbl) >= LONG_LABEL_LEN
    ]
    matches: list[Match] = []
    for line in _group_lines(words):
        line_text = normalize("".join(w.text for w in line))
        if any(d in line_text for d in deny):
            continue
        for entry in catalog.buttons:
            if entry.category == "deny":
                continue
            found = _match_line(line, line_text, entry)
            if found is not None and found.height <= MAX_LABEL_HEIGHT:
                matches.append(found)
    return _drop_implausible_repeats(matches)


def _drop_implausible_repeats(matches: list[Match]) -> list[Match]:
    """Discard every match for a label that showed up too many times.

    Caught live: a file-verification tool's result table, one "OK" per row
    (975 of them), each individually isolated enough on its own line to
    read as the "next" button - auto mode clicked one at essentially random
    coordinates every few seconds, never actually the real control, while
    reporting "running" the whole time.
    """
    counts: dict[tuple[str, str], int] = {}
    for m in matches:
        key = (m.entry.category, m.label)
        counts[key] = counts.get(key, 0) + 1
    return [
        m
        for m in matches
        if counts[(m.entry.category, m.label)] <= MAX_PLAUSIBLE_REPEATS
    ]


def _match_line(line: list[Word], line_text: str, entry: ButtonEntry) -> Match | None:
    # "finish" ends the installer (Finish, or a "late" Exit once files were
    # written). A one-typo-tolerant match on ordinary page text is common
    # enough (a short label is just as likely to be a garbled fragment of
    # something else) that the risk of quitting a live install over it is
    # not worth it - require the genuine word there, unlike every other
    # category, where a false positive just fails to advance the page.
    fuzzy = entry.category != "finish"
    for label in entry.normalized_labels:
        if (
            (entry.toggle or entry.category == "key")
            and len(label) >= LONG_LABEL_LEN
            and label in line_text
        ):
            span = _span_for_substring(line, label)
            if span is not None:
                return _build(entry, label, line, *span)
        for start in range(len(line)):
            joined = ""
            for end in range(start + 1, min(len(line), start + MAX_SPAN_WORDS) + 1):
                joined += normalize(line[end - 1].text)
                if len(joined) > len(label) + 1:
                    break
                whole = start == 0 and end == len(line)
                if _label_matches(
                    joined, label, whole, _is_isolated(line, start, end), fuzzy
                ):
                    return _build(entry, label, line, start, end)
    return None


def _span_for_substring(line: list[Word], label: str) -> tuple[int, int] | None:
    """Words covering ``label`` inside the line, tolerant of noise glued to
    the first word (a checkbox glyph read as "|_|")."""
    bounds: list[tuple[int, int]] = []
    joined = ""
    for w in line:
        start = len(joined)
        joined += normalize(w.text)
        bounds.append((start, len(joined)))
    at = joined.find(label)
    if at < 0:
        return None
    end = at + len(label)
    covered = [i for i, (a, b) in enumerate(bounds) if a < end and b > at]
    return (covered[0], covered[-1] + 1) if covered else None


def _build(
    entry: ButtonEntry, label: str, line: list[Word], start: int, end: int
) -> Match:
    span = line[start:end]
    left = min(w.left for w in span)
    top = min(w.top for w in span)
    right = max(w.right for w in span)
    bottom = max(w.bottom for w in span)
    return Match(
        entry=entry,
        label=label,
        text=" ".join(w.text for w in span),
        left=left,
        top=top,
        width=right - left,
        height=bottom - top,
    )
