from html import unescape
from html.parser import HTMLParser

_BLOCK_TAGS = frozenset(
    {
        "address",
        "article",
        "aside",
        "blockquote",
        "caption",
        "center",
        "dd",
        "details",
        "dialog",
        "div",
        "dl",
        "dt",
        "fieldset",
        "figcaption",
        "figure",
        "footer",
        "form",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "hgroup",
        "hr",
        "legend",
        "li",
        "main",
        "menu",
        "nav",
        "ol",
        "p",
        "pre",
        "search",
        "section",
        "summary",
        "table",
        "tbody",
        "td",
        "tfoot",
        "th",
        "thead",
        "tr",
        "ul",
    }
)
_INLINE_TAGS = frozenset(
    {
        "a",
        "abbr",
        "area",
        "audio",
        "b",
        "base",
        "bdi",
        "bdo",
        "big",
        "body",
        "button",
        "canvas",
        "cite",
        "code",
        "col",
        "colgroup",
        "data",
        "datalist",
        "del",
        "dfn",
        "em",
        "embed",
        "font",
        "head",
        "html",
        "i",
        "iframe",
        "img",
        "input",
        "ins",
        "kbd",
        "label",
        "link",
        "map",
        "mark",
        "meta",
        "meter",
        "noscript",
        "object",
        "optgroup",
        "option",
        "output",
        "param",
        "picture",
        "progress",
        "q",
        "rb",
        "rp",
        "rt",
        "rtc",
        "ruby",
        "s",
        "samp",
        "select",
        "selectedcontent",
        "slot",
        "small",
        "source",
        "span",
        "strike",
        "strong",
        "sub",
        "sup",
        "template",
        "textarea",
        "time",
        "title",
        "track",
        "tt",
        "u",
        "var",
        "video",
        "wbr",
    }
)
_BOOLEAN_ATTRIBUTES = frozenset(
    {
        "allowfullscreen",
        "async",
        "autofocus",
        "autoplay",
        "checked",
        "controls",
        "default",
        "defer",
        "disabled",
        "download",
        "formnovalidate",
        "hidden",
        "inert",
        "ismap",
        "itemscope",
        "loop",
        "multiple",
        "muted",
        "nomodule",
        "novalidate",
        "open",
        "playsinline",
        "readonly",
        "required",
        "reversed",
        "selected",
    }
)


class _SummaryParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.has_markup = False
        self.hidden_tag: str | None = None
        self.needs_boundary = False
        self.endtag_text = ""

    def parse_starttag(self, i: int) -> int:
        end = super().parse_starttag(i)
        if self.cdata_elem and not self.hidden_tag:
            # A literal <script ...> comparison must not hide subsequent text.
            self.clear_cdata_mode()
        return end

    def parse_endtag(self, i: int) -> int:
        # HTMLParser only exposes the original spelling for opening tags.
        self.endtag_text = self.rawdata[i : self.rawdata.find(">", i) + 1]
        return super().parse_endtag(i)

    def _boundary(self) -> None:
        self.needs_boundary = True

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.hidden_tag:
            return
        if any(
            value is None and name not in _BOOLEAN_ATTRIBUTES for name, value in attrs
        ):
            # Comparisons like a<b and c>d look like tags with bare attributes.
            self.handle_data(unescape(self.get_starttag_text() or ""))
        elif tag in {"script", "style"}:
            self.has_markup = True
            self.hidden_tag = tag
        elif tag == "br":
            self.has_markup = True
            self.handle_data("\n")
        elif tag in _BLOCK_TAGS:
            self.has_markup = True
            self._boundary()
        elif tag in _INLINE_TAGS:
            self.has_markup = True
        else:
            # Unknown tags may be literal text, such as <player> in instructions.
            self.handle_data(unescape(self.get_starttag_text() or ""))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if self.hidden_tag == tag:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if self.hidden_tag:
            if tag == self.hidden_tag:
                self.hidden_tag = None
        elif tag in _BLOCK_TAGS:
            self.has_markup = True
            self._boundary()
        elif tag in _INLINE_TAGS or tag == "br":
            self.has_markup = True
        else:
            self.handle_data(unescape(self.endtag_text))

    def handle_data(self, data: str) -> None:
        if self.hidden_tag or not data:
            return
        if (
            self.needs_boundary
            and self.parts
            and not self.parts[-1].endswith("\n")
            and not data.startswith("\n")
        ):
            self.parts.append("\n")
        self.needs_boundary = False
        self.parts.append(data)

    def handle_comment(self, data: str) -> None:
        self.has_markup = True


def normalize_summary(summary: str | None) -> str:
    """Convert provider HTML to text without reparsing decoded angle brackets."""
    if not summary:
        return ""
    parser = _SummaryParser()
    parser.feed(summary)
    # Incomplete tags at EOF may be literal text, not markup to discard.
    parser.handle_data(unescape(parser.rawdata))
    text = "".join(parser.parts)
    return text.strip() if parser.has_markup else unescape(summary)
