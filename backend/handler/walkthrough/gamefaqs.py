"""Fetch GameFAQs text guides into the walkthrough document model.

Design note: we extract plain text only and never store or serve remote HTML.
GameFAQs text guides live inside a `<pre>` (or a `#faqtext` container), so
pulling the text out sidesteps HTML sanitization entirely: nothing script
capable is ever persisted. The outbound request also rides the shared,
SSRF-protected httpx client, with an extra host allowlist below.
"""

from __future__ import annotations

from html.parser import HTMLParser
from typing import TypedDict
from urllib.parse import urlparse

from utils.context import ctx_httpx_client

# Only these hosts may be fetched. The SSRF backend already blocks internal
# addresses; this narrows outbound walkthrough fetches to GameFAQs on top.
GAMEFAQS_HOSTS = frozenset(
    {
        "gamefaqs.gamespot.com",
        "www.gamefaqs.com",
        "gamefaqs.com",
    }
)

# Cap the response we will read into memory (guides are text; 8 MiB is plenty).
MAX_GUIDE_BYTES = 8 * 1024 * 1024

_TITLE_SUFFIXES = (" - Guide and Walkthrough", " - FAQ", " - GameFAQs")


class ParsedGuide(TypedDict):
    title: str | None
    author: str | None
    text: str


class GameFAQsFetchError(Exception):
    """Raised when a GameFAQs guide cannot be fetched or parsed."""


def validate_gamefaqs_url(url: str) -> str:
    """Return the URL if it is a well-formed https GameFAQs URL, else raise."""
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError("Walkthrough URL must use https")
    host = (parsed.hostname or "").lower()
    if host not in GAMEFAQS_HOSTS:
        raise ValueError(
            "Only GameFAQs guide URLs are supported "
            f"(allowed hosts: {', '.join(sorted(GAMEFAQS_HOSTS))})"
        )
    return url


class _GuideExtractor(HTMLParser):
    """Pull the guide title, author, and body text out of a GameFAQs page.

    Body text is captured from any `<pre>` element or any element whose id or
    class contains "faqtext". Meta tags supply the title/author when present.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title: str | None = None
        self.author: str | None = None
        self._meta_title: str | None = None
        self._capture_depth = 0
        self._in_title = False
        self._title_buf: list[str] = []
        self._body_buf: list[str] = []

    @staticmethod
    def _is_capture_tag(tag: str, attrs: dict[str, str]) -> bool:
        if tag == "pre":
            return True
        ident = f"{attrs.get('id', '')} {attrs.get('class', '')}".lower()
        return "faqtext" in ident

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {k: (v or "") for k, v in attrs}

        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            name = attr_map.get("name", "").lower()
            prop = attr_map.get("property", "").lower()
            content = attr_map.get("content", "").strip()
            if content and name == "author" and not self.author:
                self.author = content[:512]
            if content and prop == "og:title" and not self._meta_title:
                self._meta_title = content

        if self._capture_depth > 0:
            self._capture_depth += 1
        elif self._is_capture_tag(tag, attr_map):
            self._capture_depth = 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if self._capture_depth > 0:
            self._capture_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_buf.append(data)
        if self._capture_depth > 0:
            self._body_buf.append(data)

    def finalize(self) -> ParsedGuide:
        raw_title = self._meta_title or "".join(self._title_buf).strip() or None
        title = _clean_title(raw_title)
        text = "".join(self._body_buf).strip()
        return ParsedGuide(title=title, author=self.author, text=text)


def _clean_title(title: str | None) -> str | None:
    if not title:
        return None
    cleaned = title.strip()
    for suffix in _TITLE_SUFFIXES:
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)].strip()
    return cleaned[:512] or None


def parse_gamefaqs_guide(html: str) -> ParsedGuide:
    """Parse a GameFAQs guide HTML string into title/author/text.

    Pure function (no I/O) so it can be unit-tested against saved fixtures.
    """
    extractor = _GuideExtractor()
    extractor.feed(html)
    extractor.close()
    return extractor.finalize()


async def fetch_gamefaqs_guide(url: str) -> ParsedGuide:
    """Fetch and parse a GameFAQs guide. Raises GameFAQsFetchError on failure."""
    validate_gamefaqs_url(url)

    client = ctx_httpx_client.get()
    try:
        response = await client.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; RomM/1.0; +https://romm.app)",
                "Accept": "text/html,application/xhtml+xml",
            },
            follow_redirects=True,
            timeout=30.0,
        )
        response.raise_for_status()
    except Exception as exc:
        raise GameFAQsFetchError(f"Could not fetch guide: {exc}") from exc

    content = response.content[:MAX_GUIDE_BYTES]
    guide = parse_gamefaqs_guide(content.decode("utf-8", errors="replace"))

    if not guide["text"]:
        raise GameFAQsFetchError(
            "No guide text found at that URL. It may be a formatted guide or "
            "an unsupported page."
        )
    return guide
