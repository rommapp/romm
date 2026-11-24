"""The choices a searchable setting offers.

A `search` field holds an id from a list only its own source knows, so RomM asks
that source as the user types and shows what comes back. Nothing is cached
beyond a short window: the list is the plugin's, and a plugin that changes its
catalogue should be visible without a restart.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Final

import httpx2
from endpoints.responses.plugin import (
    PluginOptionSchema,
    PluginOptionSourceSchema,
    PluginSettingSchema,
)
from fastapi import status
from utils.context import create_httpx_client

from handler.plugin_facts import PUBLIC_ONLY
from handler.plugin_handler import PluginRefused, PluginSchema

logger = logging.getLogger(__name__)

OPTION_TIMEOUT: Final[float] = 8.0
# A search that took this long to answer is still worth showing, but not for
# long: the next keystroke asks again.
CACHE_SECONDS: Final[float] = 60.0
MAX_OPTION_BYTES: Final[int] = 512 * 1024
# A search is cheap to repeat and expensive to keep: the cache holds the recent
# ones, not every one a server has ever answered.
MAX_CACHED_SEARCHES: Final[int] = 256

_CACHE: dict[tuple[str, str], tuple[float, list[PluginOptionSchema]]] = {}


def options_for(
    plugin: PluginSchema, key: str, query: str
) -> tuple[list[PluginOptionSchema], str | None]:
    """The choices a searchable setting offers for what the user typed.

    Args:
        plugin: The plugin whose field is being filled in.
        key: The setting's key.
        query: What the user has typed so far.

    Returns:
        tuple[list[PluginOptionSchema], str | None]: The choices, and a note
            when the source could not be asked. A source that is down empties
            the list rather than failing the form.

    Raises:
        PluginRefused: The plugin declares no such searchable setting.
    """
    setting = next(
        (
            field
            for field in _walk(plugin.settings)
            if field.key == key and field.type == "search"
        ),
        None,
    )
    if setting is None or setting.source is None:
        raise PluginRefused(f"{plugin.name} has no searchable setting called {key}")

    cache_key = (f"{plugin.id}.{key}", query.strip().lower())
    cached = _CACHE.get(cache_key)
    if cached is not None:
        if time.monotonic() - cached[0] < CACHE_SECONDS:
            return cached[1], None
        # Read, not used, and past its life: drop it rather than leave it.
        _CACHE.pop(cache_key, None)

    try:
        found = _ask(setting.source, query)
    except (ValueError, TypeError, OSError, httpx2.HTTPError, PluginRefused) as exc:
        logger.warning(f"Plugins: {plugin.id}.{key} could not be searched: {exc}")
        return [], str(exc)

    _forget_expired()
    if len(_CACHE) >= MAX_CACHED_SEARCHES:
        _CACHE.clear()
    _CACHE[cache_key] = (time.monotonic(), found)
    return found, None


def _forget_expired() -> None:
    """Drop every cached search that has outlived its window."""
    now = time.monotonic()
    for key in [k for k, (at, _) in _CACHE.items() if now - at >= CACHE_SECONDS]:
        _CACHE.pop(key, None)


def _walk(fields: list[PluginSettingSchema]) -> list[PluginSettingSchema]:
    """Every field, including the ones a group holds.

    Args:
        fields: The plugin's top-level fields.

    Returns:
        list[PluginSettingSchema]: All of them, flattened.
    """
    every: list[PluginSettingSchema] = []
    for field in fields:
        every.append(field)
        every.extend(field.fields)
    return every


def _ask(source: PluginOptionSourceSchema, query: str) -> list[PluginOptionSchema]:
    """Ask the source what it has, and read the answer.

    Args:
        source: Where to ask and how to read the reply.
        query: What the user has typed.

    Returns:
        list[PluginOptionSchema]: The choices, capped at the source's limit.

    Raises:
        ValueError: The reply is not the shape the manifest described.
        PluginRefused: The source could not be reached or refused the request.
    """
    asks_source = any("{query}" in sent for sent in source.query.values())
    # The placeholder usually sits inside a JSON blob, which is itself a query
    # parameter. Escaping for JSON and leaving the encoding to the client keeps
    # the text percent-encoded exactly once.
    params = {
        name: sent.replace("{query}", _json_safe(query))
        for name, sent in source.query.items()
    }

    payload = _fetch(source.url, params)
    items = _at(payload, source.items)
    if not isinstance(items, list):
        raise TypeError(f"{source.items} is not a list")

    # A source that cannot be asked narrows its own list: it sent the whole
    # catalogue, so the search happens here instead — before the page is cut,
    # because a match after the first `limit` entries is still a match.
    needle = "" if asks_source else query.strip().lower()

    found: list[PluginOptionSchema] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        value = _at(item, source.value)
        label = _label(item, source.label)
        if not isinstance(value, str) or not value or not label:
            continue
        if value in seen:
            continue
        if needle and needle not in label.lower():
            continue
        seen.add(value)
        found.append(PluginOptionSchema(value=value, label=label))
        if len(found) >= source.limit:
            break
    return found


def _fetch(url: str, params: dict[str, str]) -> Any:
    """Ask the source, and parse what it answers.

    Args:
        url: The address to ask.
        params: The query parameters, already filled in.

    Returns:
        Any: The parsed reply.

    Raises:
        PluginRefused: The source could not be reached, refused the request, or
            answered with more than a list.
        ValueError: The reply is not JSON.
    """
    # Public-only at connection time: an empty allowlist is what keeps a
    # private origin out even if the name resolved publicly a moment ago.
    with (
        create_httpx_client(allowlist=PUBLIC_ONLY) as client,
        client.stream(
            "GET",
            url,
            params=params,
            timeout=OPTION_TIMEOUT,
            follow_redirects=False,
        ) as response,
    ):
        if response.status_code != status.HTTP_200_OK:
            raise PluginRefused(f"{url} answered {response.status_code}")
        # Read in chunks and stop at the limit: a source that streams megabytes
        # must not decide how much memory the server spends.
        body = b""
        for chunk in response.iter_bytes():
            body += chunk
            if len(body) > MAX_OPTION_BYTES:
                raise PluginRefused(f"{url} answered with more than a list")
    return json.loads(body.decode("utf-8"))


def _at(payload: Any, path: str) -> Any:
    """The value a dotted path names.

    Args:
        payload: The parsed reply, or one of its entries.
        path: Dots between names, e.g. `result.data.json.devices`.

    Returns:
        Any: The value, or None when the path leads nowhere.
    """
    current = payload
    for part in path.split("."):
        if not part:
            continue
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list) and part.isdigit():
            index = int(part)
            current = current[index] if index < len(current) else None
        else:
            return None
        if current is None:
            return None
    return current


def _label(item: dict[str, Any], template: str) -> str:
    """The text an entry shows, from a path or a template.

    A template mixes several fields so a device reads as "Retroid Pocket 5"
    rather than "Pocket 5"; a plain path is the one field that names it.

    Args:
        item: One entry of the source's list.
        template: A dotted path, or text with `{dotted.path}` holes in it.

    Returns:
        str: The label, trimmed, or an empty string when it cannot be built.
    """
    if "{" not in template:
        found = _at(item, template)
        return found.strip() if isinstance(found, str) else ""

    def fill(match: Any) -> str:
        found = _at(item, match.group(1))
        return str(found) if isinstance(found, (str, int, float)) else ""

    import re

    text = re.sub(r"\{([^{}]+)\}", fill, template)
    # A hole that found nothing leaves a doubled space behind.
    return " ".join(text.split())


def _json_safe(text: str) -> str:
    """A quoted string's worth of text, safe to drop into a JSON template.

    Args:
        text: What the user typed.

    Returns:
        str: The text with quotes and backslashes escaped.
    """
    return text.replace("\\", "\\\\").replace('"', '\\"')
