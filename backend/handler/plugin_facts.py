"""Plugins that read a source: what a manifest is allowed to ask for, and how it
is fetched.

A plugin is a manifest, so it cannot run. What it can do is name a URL that
answers JSON, a path to the list in that answer, and the two fields to count by;
the server fetches it, and the UI draws what comes back. Nothing here knows what
EmuReady is: the manifest says where to look, this module does the looking.

A manifest is not trusted with the network: http(s) only, public addresses only
through the shared SSRF guard, no redirects, a size cap and a timeout. A source
being down is not an error the page carries; the panel comes back with the
reason in `note`.
"""

import json
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode, urlsplit

import httpx2

from endpoints.responses.plugin import (
    PluginFactGroupSchema,
    PluginFactSchema,
    PluginSlot,
)
from utils.context import create_httpx_client
from utils.ssrf import ValidationError, validate_url_for_http_request

# A source a manifest names is a URL nobody vetted, so it may only reach public
# addresses: no internal services, no metadata endpoints, nothing on the machine
# RomM itself runs on.
PUBLIC_ONLY: frozenset[tuple[str, int]] = frozenset()

# A panel is a summary, not an archive: the first page of results, capped.
MAX_FACTS: int = 4
MAX_ITEMS: int = 500
MAX_GROUPS: int = 24
MAX_GROUP_LABEL: int = 64
MAX_RESPONSE_BYTES: int = 1024 * 1024
FETCH_TIMEOUT_SECONDS: float = 8.0
CACHE_TTL_SECONDS: int = 600
CACHE_MAX_ENTRIES: int = 256

# A source's field names are dotted paths into its answer. Anything that is not
# a plain path is refused, so a manifest cannot address anything but its own JSON.
PATH_PATTERN: re.Pattern[str] = re.compile(r"^[A-Za-z0-9_-]+(\.[A-Za-z0-9_-]+){0,8}$")

_CACHE: dict[tuple[str, int, str], tuple[float, dict[str, Any]]] = {}
_CACHE_LOCK = threading.Lock()


@dataclass
class PluginFactSpec:
    """One panel a manifest declares, with everything needed to fill it."""

    id: str
    label: str
    slot: PluginSlot
    url: str
    query: dict[str, str] = field(default_factory=dict)
    list_path: str = ""
    group_by: str = ""
    rating_field: str = ""
    link: str | None = None
    # The action this panel explains, if the manifest names one.
    action: str | None = None
    limit: int = 200
    # Key of a boolean setting that must be on for the panel to be filled.
    enabled_by: str | None = None


def refused_source(url: str) -> str | None:
    """Why a URL may not be fetched, or None when it may.

    The same guard the connection uses, asked early: a manifest's author gets a
    sentence instead of a failed request.

    Args:
        url: The address the manifest resolves to.

    Returns:
        str | None: A reason fit to show a plugin's author, or None.
    """
    try:
        validate_url_for_http_request(url, allowlist=PUBLIC_ONLY)
    except ValidationError as exc:
        return exc.message
    return None


def _dig(document: Any, path: str) -> Any:
    """Follow a dotted path through a JSON document.

    Args:
        document: The parsed answer.
        path: Dots between keys; an empty path is the document itself.

    Returns:
        Any: What sits at that path, or None.
    """
    node = document
    for step in [part for part in path.split(".") if part]:
        if isinstance(node, dict):
            node = node.get(step)
        elif isinstance(node, list) and step.isdigit():
            index = int(step)
            node = node[index] if index < len(node) else None
        else:
            return None
        if node is None:
            return None
    return node


def _label(value: Any) -> str:
    """One value from a source, as a short label worth drawing."""
    if value is None:
        return "Unknown"
    text = str(value).strip()
    if not text:
        return "Unknown"
    return text[:MAX_GROUP_LABEL]


def _fetch(url: str) -> dict[str, Any]:
    """Read a JSON document, within the limits a manifest is held to.

    Args:
        url: The fully expanded address.

    Returns:
        dict[str, Any]: The parsed answer.

    Raises:
        ValueError: The source refused the read, or answered with something
            unusable.
    """
    refusal = refused_source(url)
    if refusal:
        raise ValueError(refusal)

    body = bytearray()
    try:
        # The guarded client pins the address it resolved, so a name that
        # answers one thing at validation cannot answer another at connect.
        with (
            create_httpx_client(allowlist=PUBLIC_ONLY) as client,
            client.stream(
                "GET",
                url,
                headers={"Accept": "application/json"},
                timeout=FETCH_TIMEOUT_SECONDS,
                follow_redirects=False,
            ) as reply,
        ):
            if reply.status_code != 200:
                raise ValueError(f"The source answered {reply.status_code}")
            for chunk in reply.iter_bytes():
                body.extend(chunk)
                if len(body) > MAX_RESPONSE_BYTES:
                    raise ValueError("The source answered with too much")
    except httpx2.HTTPError as exc:
        raise ValueError(f"The source could not be reached: {exc}") from exc

    try:
        document = json.loads(bytes(body))
    except ValueError as exc:
        raise ValueError("The source did not answer with JSON") from exc
    if not isinstance(document, dict):
        raise TypeError("The source did not answer with an object")
    return document


def _cached(plugin_id: str, fact_id: str, url: str) -> dict[str, Any] | None:
    key = (plugin_id, hash(fact_id), url)
    now = time.monotonic()
    with _CACHE_LOCK:
        entry = _CACHE.get(key)
        if entry is None:
            return None
        expires_at, document = entry
        if expires_at < now:
            _CACHE.pop(key, None)
            return None
    return document


def _remember(plugin_id: str, fact_id: str, url: str, document: dict[str, Any]) -> None:
    key = (plugin_id, hash(fact_id), url)
    with _CACHE_LOCK:
        if len(_CACHE) >= CACHE_MAX_ENTRIES:
            # Oldest first: the dict keeps insertion order, and a stale panel is
            # worth less than room for the game someone is looking at now.
            for stale in list(_CACHE)[: CACHE_MAX_ENTRIES // 4]:
                _CACHE.pop(stale, None)
        _CACHE[key] = (time.monotonic() + CACHE_TTL_SECONDS, document)


def fill_fact(
    plugin_id: str, spec: PluginFactSpec, url: str, link: str | None
) -> PluginFactSchema:
    """Fill one panel from its source.

    Args:
        plugin_id: The plugin the panel belongs to.
        spec: What the manifest asked for.
        url: The source address, already expanded and query-encoded.
        link: Where a reader can see the whole report, if the manifest says.

    Returns:
        PluginFactSchema: The panel, with `note` set when nothing could be read.
    """
    try:
        document = _cached(plugin_id, spec.id, url)
        if document is None:
            document = _fetch(url)
            _remember(plugin_id, spec.id, url, document)
    except (TypeError, ValueError) as exc:
        return PluginFactSchema(
            id=spec.id, label=spec.label, slot=spec.slot, link=link, note=str(exc)
        )

    items = _dig(document, spec.list_path)
    if not isinstance(items, list):
        return PluginFactSchema(
            id=spec.id,
            label=spec.label,
            slot=spec.slot,
            link=link,
            note="The source answered, but not in the shape this plugin asked for",
        )

    grouped: dict[str, dict[str, int]] = {}
    for item in items[: min(spec.limit, MAX_ITEMS)]:
        if not isinstance(item, dict):
            continue
        key = _label(_dig(item, spec.group_by))
        rating = (
            _label(_dig(item, spec.rating_field)) if spec.rating_field else "Reported"
        )
        bucket = grouped.setdefault(key, {})
        bucket[rating] = bucket.get(rating, 0) + 1

    if not grouped:
        return PluginFactSchema(
            id=spec.id,
            label=spec.label,
            slot=spec.slot,
            link=link,
            note="No reports for this title yet",
        )

    groups = [
        PluginFactGroupSchema(key=key, counts=counts, total=sum(counts.values()))
        for key, counts in grouped.items()
    ]
    groups.sort(key=lambda group: group.total, reverse=True)

    return PluginFactSchema(
        id=spec.id,
        label=spec.label,
        slot=spec.slot,
        link=link,
        groups=groups[:MAX_GROUPS],
        total=sum(group.total for group in groups),
    )


def expand_query(query: dict[str, str]) -> str:
    """A source's query string, with its values encoded once.

    Args:
        query: Parameter names and their expanded values.

    Returns:
        str: A query string, or an empty string when there is nothing to add.
    """
    if not query:
        return ""
    return urlencode({key: value for key, value in query.items()})


def source_url(base: str, query: str) -> str:
    """Join an expanded base URL with its query string.

    Args:
        base: The manifest's `url`, expanded.
        query: The encoded query string, possibly empty.

    Returns:
        str: The address to fetch.
    """
    if not query:
        return base
    separator = "&" if urlsplit(base).query else "?"
    return f"{base}{separator}{query}"


def forget_all() -> None:
    """Drop every cached panel. Used when the shelf changes."""
    with _CACHE_LOCK:
        _CACHE.clear()


def still_worth_drawing(spec: PluginFactSpec, settings: dict[str, Any]) -> bool:
    """Whether a panel's gate lets it be filled.

    Args:
        spec: The panel's declaration.
        settings: The plugin's saved values.

    Returns:
        bool: False only when the gate names a setting that is explicitly off.
    """
    if spec.enabled_by is None:
        return True
    return settings.get(spec.enabled_by) is not False


__all__ = [
    "MAX_FACTS",
    "PATH_PATTERN",
    "PluginFactSpec",
    "expand_query",
    "fill_fact",
    "forget_all",
    "refused_source",
    "source_url",
    "still_worth_drawing",
]
