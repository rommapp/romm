"""Plugins: manifests on disk that add actions to the game UI.

A plugin is a folder under PLUGINS_BASE_PATH holding a ``plugin.json``. Nothing
in it runs on the server: the manifest only says which buttons to draw and
which URL a press opens, so a plugin cannot reach past the browser it lands in.
That is why installing one needs no restart, no migration and no trust beyond
the file itself.

Manifests are validated here rather than at the endpoint, so the API keeps
answering even when one folder on the shelf is broken.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Final

from config import PLUGINS_BASE_PATH
from endpoints.responses.plugin import PluginActionSchema, PluginSchema
from logger.logger import log

MANIFEST_NAME: Final[str] = "plugin.json"

# A shelf, not a registry: this bounds the directory walk on a share the user
# controls.
MAX_PLUGINS: Final[int] = 64
MAX_MANIFEST_BYTES: Final[int] = 32 * 1024
MAX_ACTIONS: Final[int] = 8
MAX_LABEL_LENGTH: Final[int] = 48
MAX_TEXT_LENGTH: Final[int] = 200
MAX_URL_LENGTH: Final[int] = 2048

ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
SCHEME_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^(?P<scheme>[a-z][a-z0-9+.-]{1,31}):"
)
PLACEHOLDER_PATTERN: Final[re.Pattern[str]] = re.compile(r"\{([a-z_]+)\}")
WHITESPACE_PATTERN: Final[re.Pattern[str]] = re.compile(r"[\s\x00-\x1f]")

# Schemes a browser runs as markup, or reads as a local file, instead of
# handing to the OS.
BLOCKED_SCHEMES: Final[frozenset[str]] = frozenset(
    {"javascript", "data", "vbscript", "file", "blob", "about"}
)

# What a manifest may interpolate: only the game the press happened on.
ALLOWED_PLACEHOLDERS: Final[frozenset[str]] = frozenset(
    {"rom_id", "rom_name", "platform_slug", "platform_name", "file_name"}
)

WEB_SCHEMES: Final[frozenset[str]] = frozenset({"http", "https"})


def list_plugins() -> list[PluginSchema]:
    """Every valid plugin on the shelf, sorted by name.

    A manifest that fails validation is skipped with a log line: one broken
    folder must not cost the user the rest of the shelf.

    Returns:
        list[PluginSchema]: The plugins that parsed, alphabetically by name.
    """
    base = Path(PLUGINS_BASE_PATH)
    if not base.is_dir():
        return []

    try:
        folders = sorted(path for path in base.iterdir() if path.is_dir())
    except OSError as exc:
        log.warning(f"Plugins: cannot read {base}: {exc}")
        return []

    plugins: list[PluginSchema] = []
    seen: set[str] = set()
    for folder in folders[:MAX_PLUGINS]:
        raw = _read_manifest(folder / MANIFEST_NAME)
        if raw is None:
            continue
        plugin = _parse_plugin(raw, folder)
        if plugin is None:
            continue
        if plugin.id in seen:
            log.warning(f"Plugins: {folder.name} repeats the id '{plugin.id}', skipped")
            continue
        seen.add(plugin.id)
        plugins.append(plugin)

    return sorted(plugins, key=lambda plugin: plugin.name.lower())


def _read_manifest(path: Path) -> dict[str, Any] | None:
    try:
        if not path.is_file() or path.stat().st_size > MAX_MANIFEST_BYTES:
            if path.exists():
                log.warning(
                    f"Plugins: {path} is larger than {MAX_MANIFEST_BYTES} bytes"
                )
            return None
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        log.warning(f"Plugins: cannot read {path}: {exc}")
        return None

    if not isinstance(raw, dict):
        log.warning(f"Plugins: {path} is not a JSON object")
        return None
    return raw


def _parse_plugin(raw: dict[str, Any], folder: Path) -> PluginSchema | None:
    plugin_id = _slug(raw.get("id"))
    name = _text(raw.get("name"), MAX_TEXT_LENGTH)
    if not plugin_id or not name:
        log.warning(f"Plugins: {folder.name} needs an 'id' and a 'name'")
        return None

    raw_actions = raw.get("actions")
    if not isinstance(raw_actions, list):
        raw_actions = []

    actions: list[PluginActionSchema] = []
    action_ids: set[str] = set()
    for raw_action in raw_actions[:MAX_ACTIONS]:
        if not isinstance(raw_action, dict):
            continue
        action = _parse_action(raw_action, plugin_id)
        if action is None or action.id in action_ids:
            continue
        action_ids.add(action.id)
        actions.append(action)

    if not actions:
        log.warning(f"Plugins: {plugin_id} declares no usable action, skipped")
        return None

    homepage = _text(raw.get("homepage"), MAX_URL_LENGTH)
    if homepage and not _is_web_url(homepage):
        homepage = None

    return PluginSchema(
        id=plugin_id,
        name=name,
        version=_text(raw.get("version"), MAX_TEXT_LENGTH) or "0.0.0",
        description=_text(raw.get("description"), MAX_TEXT_LENGTH),
        author=_text(raw.get("author"), MAX_TEXT_LENGTH),
        homepage=homepage,
        actions=actions,
    )


def _parse_action(raw: dict[str, Any], plugin_id: str) -> PluginActionSchema | None:
    action_id = _slug(raw.get("id"))
    label = _text(raw.get("label"), MAX_LABEL_LENGTH)
    url = _text(raw.get("url"), MAX_URL_LENGTH)
    if not action_id or not label or not url:
        log.warning(
            f"Plugins: {plugin_id} has an action without an 'id', 'label' or 'url'"
        )
        return None

    reason = _url_refusal(url)
    if reason:
        log.warning(f"Plugins: {plugin_id}.{action_id} has an unusable url: {reason}")
        return None

    open_mode = raw.get("open")
    return PluginActionSchema(
        id=action_id,
        label=label,
        icon=_icon(raw.get("icon")),
        url=url,
        open="same-tab" if open_mode == "same-tab" else "new-tab",
    )


def _url_refusal(url: str) -> str | None:
    """Why this URL template cannot be shipped to the browser, or None.

    Args:
        url: The manifest's URL template.

    Returns:
        str | None: A short reason for the log, or None when it is safe.
    """
    if WHITESPACE_PATTERN.search(url):
        return "contains whitespace or control characters"
    match = SCHEME_PATTERN.match(url)
    if not match:
        return "has no scheme"
    if match.group("scheme") in BLOCKED_SCHEMES:
        return f"uses the blocked scheme '{match.group('scheme')}'"
    unknown = set(PLACEHOLDER_PATTERN.findall(url)) - ALLOWED_PLACEHOLDERS
    if unknown:
        return f"uses unknown placeholders: {', '.join(sorted(unknown))}"
    return None


def _is_web_url(value: str) -> bool:
    match = SCHEME_PATTERN.match(value)
    return bool(match and match.group("scheme") in WEB_SCHEMES)


def _slug(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value if ID_PATTERN.match(value) else None


def _text(value: Any, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value or len(value) > limit:
        return None
    return value


def _icon(value: Any) -> str | None:
    """An icon name the UI can resolve, or None to fall back to its default."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value or len(value) > 64 or WHITESPACE_PATTERN.search(value):
        return None
    if not re.fullmatch(r"[A-Za-z0-9:_-]+", value):
        return None
    return value
