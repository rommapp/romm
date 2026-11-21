import re
from html.parser import HTMLParser
from typing import Final

_BREAK_TAGS: Final = frozenset({"br"})
_LINE_TAGS: Final = frozenset({"li", "tr", "dt", "dd"})
_BLOCK_TAGS: Final = frozenset(
    {
        "address",
        "article",
        "aside",
        "blockquote",
        "center",
        "dl",
        "div",
        "figure",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "hr",
        "ol",
        "p",
        "pre",
        "section",
        "table",
        "ul",
    }
)
_INLINE_TAGS: Final = frozenset(
    {
        "a",
        "abbr",
        "b",
        "big",
        "cite",
        "code",
        "del",
        "em",
        "font",
        "i",
        "img",
        "ins",
        "kbd",
        "mark",
        "q",
        "s",
        "small",
        "span",
        "strike",
        "strong",
        "sub",
        "sup",
        "tbody",
        "tfoot",
        "thead",
        "tt",
        "u",
        "wbr",
    }
)
_CELL_TAGS: Final = frozenset({"td", "th"})
_SKIP_CONTENT_TAGS: Final = frozenset({"script", "style"})
_KNOWN_TAGS: Final = (
    _BREAK_TAGS
    | _LINE_TAGS
    | _BLOCK_TAGS
    | _INLINE_TAGS
    | _CELL_TAGS
    | _SKIP_CONTENT_TAGS
)

_TRAILING_SPACE = re.compile(r"[ \t]+\n")
_LEADING_SPACE = re.compile(r"\n[ \t]+")
_EXTRA_BLANK_LINES = re.compile(r"\n{3,}")


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0
        # Set after "• " so the item's first text lands on the bullet's line.
        self._bullet_pending = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in _KNOWN_TAGS:
            # Plain text such as "<Insert Name>" parses as a tag; keep it verbatim.
            self._bullet_pending = False
            self.parts.append(self.get_starttag_text() or "")
        elif tag in _SKIP_CONTENT_TAGS:
            self._skip_depth += 1
        elif tag in _CELL_TAGS:
            self.parts.append(" ")
        elif tag == "li":
            self._bullet_pending = True
            self.parts.append("\n• ")
        elif self._bullet_pending:
            pass
        elif tag in _BREAK_TAGS:
            self.parts.append("\n")
        elif tag in _LINE_TAGS:
            self.parts.append("\n")
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n\n")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _KNOWN_TAGS:
            self.handle_starttag(tag, attrs)
        else:
            self._bullet_pending = False
            self.parts.append(self.get_starttag_text() or "")

    def handle_endtag(self, tag: str) -> None:
        if tag not in _KNOWN_TAGS:
            self.parts.append(f"</{tag}>")
        elif tag in _SKIP_CONTENT_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._bullet_pending:
            if data.isspace():
                return
            data = data.lstrip()
            self._bullet_pending = False
        self.parts.append(data)


def html_to_text(value: str | None) -> str:
    """Turn provider HTML into plain text, keeping paragraphs and line breaks as newlines."""
    if not value:
        return ""
    if "<" not in value and "&" not in value:
        return value.strip()

    parser = _TextExtractor()
    parser.feed(value)
    # An unterminated "<..." at the end is plain text the parser would drop.
    tail_start = parser.rawdata.find("<")
    tail = parser.rawdata[tail_start:] if tail_start >= 0 else ""
    if tail:
        parser.rawdata = parser.rawdata[:tail_start]
    parser.close()
    parser.parts.append(tail)
    text = "".join(parser.parts).replace("\xa0", " ")
    text = _TRAILING_SPACE.sub("\n", text)
    text = _LEADING_SPACE.sub("\n", text)
    return _EXTRA_BLANK_LINES.sub("\n\n", text).strip()
