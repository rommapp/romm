import enum
import re
from typing import Final, TypedDict

import httpx
from bs4 import BeautifulSoup, Tag

from logger.logger import log
from utils.context import ctx_httpx_client


class WalkthroughSource(enum.StrEnum):
    GAMEFAQS = "GAMEFAQS"
    UPLOAD = "UPLOAD"


class WalkthroughFormat(enum.StrEnum):
    HTML = "html"
    TEXT = "text"
    PDF = "pdf"


class WalkthroughResult(TypedDict):
    url: str
    title: str | None
    author: str | None
    source: WalkthroughSource
    format: WalkthroughFormat
    content: str


class WalkthroughError(Exception):
    """Base exception for walkthrough errors."""


class WalkthroughFetchFailed(WalkthroughError):
    """Raised when the walkthrough fetch fails."""


class InvalidWalkthroughURLError(WalkthroughError):
    """Raised when the provided URL does not match a supported source."""


class WalkthroughContentNotFound(WalkthroughError):
    """Raised when the walkthrough content cannot be extracted."""


GAMEFAQS_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^https://gamefaqs\.gamespot\.com/[^/]+/[^/]+/faqs/.+$"
)

ALLOWED_ATTRIBUTES: Final[set[str]] = {"href", "src", "alt", "title"}
ALLOWED_TAGS: Final[set[str]] = {
    "a",
    "b",
    "blockquote",
    "br",
    "code",
    "div",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "i",
    "img",
    "li",
    "ol",
    "p",
    "pre",
    "span",
    "strong",
    "table",
    "tbody",
    "td",
    "th",
    "thead",
    "tr",
    "ul",
}
ALLOWED_SCHEMES: Final[set[str]] = {"http", "https"}
UNWANTED_SELECTORS: Final[tuple[str, ...]] = (".ach-panel", ".lazyYT", ".disclaimer")
DEFAULT_HEADERS: Final[dict[str, str]] = {
    "User-Agent": "RomM/0.0.1 (+https://romm.app)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.8",
}
MAX_UPLOAD_BYTES: Final[int] = 15 * 1024 * 1024  # 15 MB
ALLOWED_MIME_TYPES: Final[set[str]] = {
    "text/plain",
    "text/html",
    "application/pdf",
    "application/xhtml+xml",
}


def is_gamefaqs_url(url: str) -> bool:
    return bool(GAMEFAQS_PATTERN.match(url))


def match_url(url: str) -> WalkthroughSource | None:
    if is_gamefaqs_url(url):
        return WalkthroughSource.GAMEFAQS
    return None


def _strip_unwanted_attributes(node: Tag) -> None:
    for tag in node.find_all(True):
        for attr in list(tag.attrs):
            if attr not in ALLOWED_ATTRIBUTES:
                tag.attrs.pop(attr, None)


def _remove_unwanted_elements(node: Tag) -> None:
    for selector in UNWANTED_SELECTORS:
        for match in node.select(selector):
            match.decompose()

    for tag in node.find_all(["script", "style", "noscript"]):
        tag.decompose()


def _remove_empty_elements(node: Tag) -> None:
    for tag_name in ("div", "span", "p"):
        for tag in list(node.find_all(tag_name)):
            if not tag.get_text(strip=True) and not tag.find("img"):
                tag.decompose()


def _is_allowed_url(value: str) -> bool:
    value = value.strip()
    if not value:
        return False
    if value.startswith("//"):
        return True
    match = re.match(r"^(?P<scheme>[a-zA-Z][a-zA-Z0-9+.-]*):", value)
    if not match:
        return True
    return match.group("scheme").lower() in ALLOWED_SCHEMES


def _remove_disallowed_tags(node: Tag) -> None:
    for tag in list(node.find_all(True)):
        if tag.name not in ALLOWED_TAGS:
            tag.decompose()
            continue

        if tag.name == "a":
            href = tag.get("href")
            if href and not _is_allowed_url(href):
                tag.attrs.pop("href", None)
        if tag.name == "img":
            src = tag.get("src")
            if src and not _is_allowed_url(src):
                tag.decompose()


def _sanitize_node(node: Tag) -> None:
    _remove_unwanted_elements(node)
    _remove_empty_elements(node)
    _remove_disallowed_tags(node)
    _strip_unwanted_attributes(node)


def _serialize_html(nodes: list[Tag]) -> str:
    """Serialize cleaned HTML fragments into a single string."""
    return "\n\n".join(node.decode(formatter="html") for node in nodes).strip()


def sanitize_html_fragment(html: str) -> str:
    """Clean arbitrary HTML input to avoid XSS."""
    soup = BeautifulSoup(html, "html.parser")
    _sanitize_node(soup)
    return _serialize_html([soup])


def _build_client(client: httpx.AsyncClient | None) -> tuple[httpx.AsyncClient, bool]:
    """Return an httpx client and whether it should be closed by the caller."""
    if client:
        return client, False

    try:
        ctx_client = ctx_httpx_client.get()
    except LookupError:
        ctx_client = None

    if ctx_client:
        return ctx_client, False

    return httpx.AsyncClient(), True


async def _fetch_html(url: str, client: httpx.AsyncClient | None = None) -> str:
    http_client, should_close = _build_client(client)
    try:
        response = await http_client.get(url, timeout=30, headers=DEFAULT_HEADERS)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        log.error("Failed to fetch walkthrough", exc_info=True)
        raise WalkthroughFetchFailed(
            f"Failed to fetch walkthrough content (status {exc.response.status_code})"
        ) from exc
    except httpx.HTTPError as exc:
        log.error("Failed to fetch walkthrough", exc_info=True)
        raise WalkthroughFetchFailed("Failed to fetch walkthrough content") from exc
    finally:
        if should_close:
            await http_client.aclose()

    return response.text


def _parse_gamefaqs(html: str) -> tuple[str | None, str | None, str]:
    soup = BeautifulSoup(html, "html.parser")
    pre_tags = soup.select("#faqtext pre")
    if not pre_tags:
        raise WalkthroughContentNotFound("Guide content not found")

    title = None
    author = None

    title_tag = soup.select_one("h2.title, h2.text")
    if title_tag:
        title = title_tag.get_text(strip=True)

    author_tag = soup.select_one(".contrib1")
    if author_tag:
        author = author_tag.get_text(strip=True)

    # GameFAQs content is always converted to clean text format
    return title, author, "\n\n".join(pre.get_text() for pre in pre_tags).strip()


async def fetch_walkthrough(
    url: str,
    client: httpx.AsyncClient | None = None,
) -> WalkthroughResult:
    source = match_url(url)
    if not source:
        raise InvalidWalkthroughURLError(
            "URL is not a supported walkthrough source (GameFAQs only)"
        )

    html = await _fetch_html(url, client)

    title, author, content = _parse_gamefaqs(html)

    return WalkthroughResult(
        url=url,
        title=title,
        author=author,
        source=source,
        format=WalkthroughFormat.TEXT,
        content=content,
    )
