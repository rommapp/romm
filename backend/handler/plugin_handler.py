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
import os
import re
import shutil
import threading
from pathlib import Path
from typing import Any, Final
from urllib.parse import quote, urlsplit

import httpx
from config import PLUGINS_BASE_PATH
from endpoints.responses.plugin import (
    PluginActionSchema,
    PluginFactSummarySchema,
    PluginSchema,
    PluginSettingOptionSchema,
    PluginSettingSchema,
    PluginSlot,
    StorePluginSchema,
)
from logger.logger import log

from handler.plugin_facts import (
    MAX_FACTS,
    PATH_PATTERN,
    PluginFactSpec,
    forget_all,
)

MANIFEST_NAME: Final[str] = "plugin.json"
SETTINGS_NAME: Final[str] = "settings.json"

# The curated index a server offers in Settings, Plugins, Add plugin. A store is
# a JSON file listing manifests by URL; nothing is fetched until someone opens
# the store or installs from it.
STORE_URL: Final[str] = (
    "https://raw.githubusercontent.com/jkoehler11/romm-plugins/main/index.json"
)
MAX_STORE_BYTES: Final[int] = 256 * 1024
MAX_SETTINGS: Final[int] = 16
MAX_SETTING_OPTIONS: Final[int] = 12
MAX_STORE_PLUGINS: Final[int] = 100
MAX_STORE_TAGS: Final[int] = 6
SETTING_TYPES: Final[frozenset[str]] = frozenset(
    {"text", "url", "number", "boolean", "select", "password"}
)

# A shelf, not a registry: this bounds the directory walk on a share the user
# controls.
MAX_PLUGINS: Final[int] = 64
MAX_MANIFEST_BYTES: Final[int] = 32 * 1024
MAX_ACTIONS: Final[int] = 8
MAX_PLATFORMS: Final[int] = 64
MAX_LABEL_LENGTH: Final[int] = 48
MAX_TEXT_LENGTH: Final[int] = 200
MAX_URL_LENGTH: Final[int] = 2048
MAX_ICON_LENGTH: Final[int] = 64

ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
SCHEME_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^(?P<scheme>[a-z][a-z0-9+.-]{1,31}):"
)
PLACEHOLDER_PATTERN: Final[re.Pattern[str]] = re.compile(r"\{([a-z_]+)\}")
# What a plugin's own settings fill in. The browser does the same substitution
# with the values the user saved; here the manifest's defaults stand in, which
# is enough to know the URL is shippable at all.
SETTING_PLACEHOLDER: Final[re.Pattern[str]] = re.compile(r"\{setting\.([a-z_]+)\}")
WHITESPACE_PATTERN: Final[re.Pattern[str]] = re.compile(r"[\s\x00-\x1f]")
ICON_PATTERN: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9:_-]+")

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

# Every place a manifest may put an action. A slot the UI does not render would
# be a button nobody sees, so an unknown one is refused rather than kept.
SLOTS: Final[frozenset[str]] = frozenset(
    {"game.details", "game.play", "app.nav", "settings.page"}
)
DEFAULT_SLOT: Final[str] = "game.details"

# One parse per shelf state: every mounted game view asks for this list, and the
# shelf can sit on a network share. Keyed by the resolved base path.
_CACHE: dict[str, tuple[tuple[tuple[str, int, int], ...], list[PluginSchema]]] = {}
_CACHE_LOCK = threading.Lock()

# What each plugin asked to read, kept out of the response: the fetch belongs to
# the server, and a manifest's request should not be readable by every client.
_FACTS_BY_ID: dict[str, list[PluginFactSpec]] = {}


def find_facts(plugin_id: str) -> list[PluginFactSpec]:
    """The panels a plugin declared.

    Args:
        plugin_id: The id the manifest declares.

    Returns:
        list[PluginFactSpec]: One entry per panel, in the order declared.
    """
    return list(_FACTS_BY_ID.get(plugin_id, []))


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

    candidates = _candidates(base)
    if not candidates:
        return []
    stamp = tuple(candidates)

    with _CACHE_LOCK:
        cached = _CACHE.get(str(base))
    if cached and cached[0] == stamp:
        return cached[1]

    plugins: list[PluginSchema] = []
    facts: dict[str, list[PluginFactSpec]] = {}
    seen: set[str] = set()
    for manifest_path, _, _ in candidates:
        path = Path(manifest_path)
        raw = _read_manifest(path)
        if raw is None:
            continue
        parsed = _parse_plugin(raw, path.parent)
        if parsed is None:
            continue
        plugin, specs = parsed
        if plugin.id in seen:
            log.warning(
                f"Plugins: {plugin.id} is on the shelf twice, keeping the first"
            )
            continue
        seen.add(plugin.id)
        plugins.append(plugin)
        if specs:
            facts[plugin.id] = specs

    plugins.sort(key=lambda plugin: plugin.name.lower())
    with _CACHE_LOCK:
        _CACHE[str(base)] = (stamp, plugins)
        _FACTS_BY_ID.clear()
        _FACTS_BY_ID.update(facts)
    # What was read for the old shelf may not be what the new one asks for.
    forget_all()
    log.info(f"Plugins: {len(plugins)} on the shelf at {base}")
    return plugins


def _candidates(base: Path) -> list[tuple[str, int, int]]:
    """Every readable manifest on the shelf, with the stat that fingerprints it.

    A folder with no manifest is not a plugin and passes in silence; a manifest
    that resolves outside the shelf, or is not a regular file, is reported and
    skipped.

    Args:
        base: The plugins folder.

    Returns:
        list[tuple[str, int, int]]: Resolved manifest path, mtime and size.
    """
    found: list[tuple[str, int, int]] = []
    try:
        folders = sorted(path for path in base.iterdir() if path.is_dir())
    except OSError as exc:
        log.warning(f"Plugins: cannot read {base}: {exc}")
        return found

    resolved_base = base.resolve()
    for folder in folders[:MAX_PLUGINS]:
        manifest_path = folder / MANIFEST_NAME
        if not manifest_path.exists():
            continue
        try:
            resolved = manifest_path.resolve(strict=True)
            info = resolved.stat()
        except (OSError, RuntimeError) as exc:
            log.warning(f"Plugins: cannot resolve {manifest_path}: {exc}")
            continue
        if resolved_base not in resolved.parents:
            # Following a symlink out of the shelf would turn a manifest path
            # into a way to read something else, so it is refused.
            log.warning(f"Plugins: {manifest_path} points outside {base}, skipped")
            continue
        if not resolved.is_file():
            log.warning(f"Plugins: {manifest_path} is not a file, skipped")
            continue
        found.append((str(resolved), info.st_mtime_ns, info.st_size))
    return found


def _read_manifest(path: Path) -> dict[str, Any] | None:
    try:
        if path.stat().st_size > MAX_MANIFEST_BYTES:
            log.warning(f"Plugins: {path} is larger than {MAX_MANIFEST_BYTES} bytes")
            return None
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        log.warning(f"Plugins: cannot read {path}: {exc}")
        return None

    if not isinstance(raw, dict):
        log.warning(f"Plugins: {path} is not a JSON object")
        return None
    return raw


def _parse_plugin(
    raw: dict[str, Any], folder: Path
) -> tuple[PluginSchema, list[PluginFactSpec]] | None:
    folder_name = folder.name
    plugin_id = _slug(raw.get("id"))
    name = _text(raw.get("name"), MAX_TEXT_LENGTH)
    if not plugin_id or not name:
        log.warning(f"Plugins: {folder_name} needs an 'id' and a 'name'")
        return None

    # A parked plugin keeps its folder and its file, and adds nothing.
    if raw.get("enabled") is False:
        log.info(f"Plugins: {plugin_id} is parked with 'enabled': false")
        return None

    # Settings first: an action's URL may be built out of them, and its defaults
    # are what says whether that URL is shippable at all.
    settings: list[PluginSettingSchema] = []
    raw_settings = raw.get("settings")
    if isinstance(raw_settings, list):
        keys: set[str] = set()
        for raw_setting in raw_settings[:MAX_SETTINGS]:
            setting = _parse_setting(raw_setting, plugin_id)
            if setting is None or setting.key in keys:
                continue
            keys.add(setting.key)
            settings.append(setting)
    defaults = {setting.key: setting.default for setting in settings}

    raw_actions = raw.get("actions")
    if not isinstance(raw_actions, list):
        raw_actions = []

    actions: list[PluginActionSchema] = []
    action_ids: set[str] = set()
    for raw_action in raw_actions:
        if not isinstance(raw_action, dict) or len(actions) >= MAX_ACTIONS:
            continue
        action = _parse_action(raw_action, plugin_id, defaults)
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

    # An action switched off by a setting needs a boolean setting to switch.
    for action in actions:
        gate = action.enabled_by
        if gate is None:
            continue
        setting = next((s for s in settings if s.key == gate), None)
        if setting is None or setting.type != "boolean":
            log.warning(
                f"Plugins: {plugin_id}.{action.id} is switched by {gate!r}, which is "
                "not a boolean setting"
            )
            action.enabled_by = None

    summaries, specs = _parse_facts(
        raw.get("facts"), plugin_id, defaults, settings, action_ids
    )

    return PluginSchema(
        id=plugin_id,
        name=name,
        version=_text(raw.get("version"), MAX_TEXT_LENGTH) or "0.0.0",
        description=_text(raw.get("description"), MAX_TEXT_LENGTH),
        author=_text(raw.get("author"), MAX_TEXT_LENGTH),
        homepage=homepage,
        actions=actions,
        settings=settings,
        facts=summaries,
    ), specs


def _with_defaults(template: str, defaults: dict[str, Any]) -> str:
    """A URL template with the plugin's own settings filled from their defaults.

    Args:
        template: The manifest's `url`.
        defaults: One value per setting the manifest declares.

    Returns:
        str: The template with `{setting.key}` replaced, rom placeholders left.
    """

    def substitute(match: re.Match[str]) -> str:
        value = defaults.get(match.group(1))
        return "" if value is None else str(value)

    return SETTING_PLACEHOLDER.sub(substitute, template)


def expand_template(
    template: str,
    rom_values: dict[str, str],
    settings: dict[str, Any],
    encode_rom: bool = False,
) -> str:
    """Fill a manifest's template, on the server, for one request.

    The browser does the same for an action's URL; a source is fetched here, so
    the same placeholders are filled the same way — settings first, then the
    game, with the game's values encoded because they end up in a query.

    Args:
        template: The manifest's url, query value or link.
        rom_values: What the game contributes.
        settings: The plugin's saved values.
        encode_rom: Whether the game's values are encoded here. A query value is
            encoded once, by the query builder, so it asks for the raw text.

    Returns:
        str: The template with placeholders replaced.
    """

    def substitute_setting(match: re.Match[str]) -> str:
        value = settings.get(match.group(1))
        return "" if value is None else str(value)

    with_settings = SETTING_PLACEHOLDER.sub(substitute_setting, template)

    def substitute_rom(match: re.Match[str]) -> str:
        value = rom_values.get(match.group(1), "")
        return quote(value, safe="") if encode_rom else value

    return PLACEHOLDER_PATTERN.sub(substitute_rom, with_settings)


def _parse_facts(
    raw: Any,
    plugin_id: str,
    defaults: dict[str, Any],
    settings: list[PluginSettingSchema],
    action_ids: set[str],
) -> tuple[list[PluginFactSummarySchema], list[PluginFactSpec]]:
    """Read the panels a manifest asks to fill from a source.

    A panel names a URL that answers JSON, the path to the list in that answer,
    and the two fields to count by. Everything is checked here, against the
    defaults the manifest also declares, so a panel that could not work is
    dropped at install time rather than discovered on a game page.

    Args:
        raw: The manifest's `facts` value.
        plugin_id: The plugin the panels belong to.
        defaults: One value per setting the manifest declares.
        settings: The settings themselves, for validating a panel's gate.
        action_ids: The actions that parsed, so a panel can only explain one of
            them.

    Returns:
        tuple[list[PluginFactSummarySchema], list[PluginFactSpec]]: What the UI
            is told about, and what the server needs to fill them.
    """
    if not isinstance(raw, list):
        return [], []

    summaries: list[PluginFactSummarySchema] = []
    specs: list[PluginFactSpec] = []
    for raw_fact in raw[:MAX_FACTS]:
        if not isinstance(raw_fact, dict) or len(specs) >= MAX_FACTS:
            continue
        fact_id = _slug(raw_fact.get("id"))
        label = _text(raw_fact.get("label"), MAX_LABEL_LENGTH)
        url = raw_fact.get("url")
        list_path = raw_fact.get("list_path")
        if not fact_id or not label or not isinstance(url, str):
            log.warning(f"Plugins: {plugin_id} has a panel with no id, label or url")
            continue
        if not isinstance(list_path, str) or not PATH_PATTERN.match(list_path):
            log.warning(f"Plugins: {plugin_id}.{fact_id} names no usable list_path")
            continue
        # Judged on its defaults, like an action's URL: a panel whose default
        # address is not fetchable cannot start working by being installed.
        reason = _url_refusal(_with_defaults(url, defaults))
        if reason:
            log.warning(f"Plugins: {plugin_id}.{fact_id} source refused: {reason}")
            continue

        query: dict[str, str] = {}
        raw_query = raw_fact.get("query")
        if isinstance(raw_query, dict):
            for name, value in list(raw_query.items())[:8]:
                if not isinstance(name, str) or not isinstance(
                    value, (str, int, float)
                ):
                    continue
                if not re.match(r"^[A-Za-z0-9_.-]{1,64}$", name):
                    continue
                query[name] = str(value)[:1024]

        link = raw_fact.get("link")
        if isinstance(link, str):
            expanded = _with_defaults(link, defaults)
            link = link if not _url_refusal(expanded) else None
        else:
            link = None

        limit = raw_fact.get("limit")
        if not isinstance(limit, int) or isinstance(limit, bool):
            limit = 200
        limit = max(1, min(limit, 500))

        gate = raw_fact.get("enabled_by")
        enabled_by = _slug(gate) if isinstance(gate, str) else None
        if enabled_by is not None:
            setting = next((s for s in settings if s.key == enabled_by), None)
            if setting is None or setting.type != "boolean":
                log.warning(
                    f"Plugins: {plugin_id}.{fact_id} is switched by {enabled_by!r}, "
                    "which is not a boolean setting"
                )
                enabled_by = None

        slot = raw_fact.get("slot")
        chosen: PluginSlot = slot if slot in SLOTS else DEFAULT_SLOT

        # A panel may explain one action's button. Naming an action that does
        # not exist is a manifest mistake, and a panel nobody can hover is not
        # worth keeping the tie for.
        action_ref = raw_fact.get("action")
        action_id = _slug(action_ref) if isinstance(action_ref, str) else None
        if action_id is not None and action_id not in action_ids:
            log.warning(
                f"Plugins: {plugin_id}.{fact_id} explains an action {action_id!r} "
                "the manifest does not have"
            )
            action_id = None

        specs.append(
            PluginFactSpec(
                id=fact_id,
                label=label,
                slot=chosen,
                url=url,
                query=query,
                list_path=list_path,
                group_by=str(raw_fact.get("group_by") or ""),
                rating_field=str(raw_fact.get("rating_field") or ""),
                link=link,
                action=action_id,
                limit=limit,
                enabled_by=enabled_by,
            )
        )
        summaries.append(
            PluginFactSummarySchema(
                id=fact_id, label=label, slot=chosen, action=action_id
            )
        )

    return summaries, specs


def _parse_action(
    raw: dict[str, Any], plugin_id: str, defaults: dict[str, Any] | None = None
) -> PluginActionSchema | None:
    action_id = _slug(raw.get("id"))
    label = _text(raw.get("label"), MAX_LABEL_LENGTH)
    url = _text(raw.get("url"), MAX_URL_LENGTH)
    if not action_id or not label or not url:
        log.warning(
            f"Plugins: {plugin_id} has an action without an 'id', 'label' or 'url'"
        )
        return None

    # A URL built entirely from a setting has no scheme until one exists, so it
    # is judged on what its defaults produce.
    reason = _url_refusal(_with_defaults(url, defaults or {}))
    if reason:
        log.warning(f"Plugins: {plugin_id}.{action_id} has an unusable url: {reason}")
        return None

    platforms = _platforms(raw.get("platforms"), plugin_id, action_id)
    if platforms is None:
        return None

    slot = _slot(raw, plugin_id, action_id)
    if slot is None:
        return None

    open_mode = raw.get("open")
    return PluginActionSchema(
        id=action_id,
        label=label,
        icon=_icon(raw.get("icon")),
        image=_image(raw.get("image")),
        url=url,
        open="same-tab" if open_mode == "same-tab" else "new-tab",
        slot=slot,
        platforms=platforms,
        enabled_by=_slug(raw.get("enabled_by")) or None,
    )


def _platforms(value: Any, plugin_id: str, action_id: str) -> list[str] | None:
    """The platform slugs an action is offered on, empty for every platform.

    Args:
        value: The manifest's `platforms`, as written.
        plugin_id: The owning plugin, for the log line.
        action_id: The action, for the log line.

    Returns:
        list[str] | None: The slugs, or None when the field is malformed.
    """
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > MAX_PLATFORMS:
        log.warning(f"Plugins: {plugin_id}.{action_id} has an unusable 'platforms'")
        return None
    slugs: list[str] = []
    for entry in value:
        slug = _slug(entry)
        if not slug:
            log.warning(
                f"Plugins: {plugin_id}.{action_id} names an unusable platform {entry!r}"
            )
            return None
        if slug not in slugs:
            slugs.append(slug)
    return slugs


def _slot(raw: dict[str, Any], plugin_id: str, action_id: str) -> PluginSlot | None:
    """Where the action belongs, or None when the manifest names nowhere.

    `play: true` from the first cut of this feature means the Play menu, so it
    keeps working as that slot rather than being a second field to explain.

    Args:
        raw: The action, as written.
        plugin_id: The owning plugin, for the log line.
        action_id: The action, for the log line.

    Returns:
        PluginSlot | None: The slot to render into.
    """
    if raw.get("play") is True and "slot" not in raw:
        return "game.play"

    slot = raw.get("slot", DEFAULT_SLOT)
    if not isinstance(slot, str) or slot not in SLOTS:
        log.warning(f"Plugins: {plugin_id}.{action_id} names an unknown slot {slot!r}")
        return None
    return slot  # type: ignore[return-value]  # narrowed by the membership check


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
    value = value.strip().lower()
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
    if not value or len(value) > MAX_ICON_LENGTH or not ICON_PATTERN.fullmatch(value):
        return None
    return value


def _image(value: Any) -> str | None:
    """A logo URL the UI paints in place of an icon, or None.

    Args:
        value: The manifest's `image`, as written.

    Returns:
        str | None: The URL when it is a web URL, else None.
    """
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value or len(value) > MAX_URL_LENGTH or WHITESPACE_PATTERN.search(value):
        return None
    return value if _is_web_url(value) else None


class PluginRefused(Exception):
    """A manifest the shelf will not take, with the reason to show the user."""


def install_plugin(
    manifest: dict[str, Any] | None = None,
    url: str | None = None,
) -> PluginSchema:
    """Put a manifest on the shelf, either pasted or fetched from a URL.

    The manifest is validated the same way a file on disk is, so an install can
    never store something the reader would then refuse. Only http(s) is
    fetched, and only up to the same size limit as a file on disk.

    Args:
        manifest: A manifest the caller already has, from a paste or upload.
        url: A URL to a manifest, fetched by the server.

    Returns:
        PluginSchema: The plugin as the UI will read it.

    Raises:
        PluginRefused: The source cannot be fetched, is not a manifest, or is
            already installed.
    """
    if manifest is None:
        if not url:
            raise PluginRefused("Name a URL or send a manifest")
        manifest = _fetch_json(url, MAX_MANIFEST_BYTES, "that URL")

    folder_name = _slug(manifest.get("id"))
    if not folder_name:
        raise PluginRefused("The manifest needs an 'id'")

    base = Path(PLUGINS_BASE_PATH)
    parsed = _parse_plugin(manifest, base / folder_name)
    plugin = parsed[0] if parsed else None
    if plugin is None:
        raise PluginRefused("The manifest is not a usable plugin")

    payload = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
    if len(payload) > MAX_MANIFEST_BYTES:
        raise PluginRefused("The manifest is too large")

    folder = base / folder_name
    try:
        base.mkdir(parents=True, exist_ok=True)
        if folder.exists():
            raise PluginRefused(f"{plugin.name} is already installed")
        folder.mkdir()
    except OSError as exc:
        raise PluginRefused(f"Cannot write to the plugins folder: {exc}") from exc

    # Written beside its final name and moved into place, so a reader never
    # sees half a manifest.
    staging = folder / f".{MANIFEST_NAME}.tmp"
    try:
        staging.write_bytes(payload)
        staging.replace(folder / MANIFEST_NAME)
    except OSError as exc:
        shutil.rmtree(folder, ignore_errors=True)
        raise PluginRefused(f"Cannot write the manifest: {exc}") from exc

    _forget(base)
    forget_all()
    log.info(f"Plugins: installed {plugin.id} from {'a URL' if url else 'a manifest'}")
    return plugin


def remove_plugin(plugin_id: str) -> None:
    """Delete a plugin's folder from the shelf.

    Args:
        plugin_id: The id the manifest declares.

    Raises:
        PluginRefused: The id is not a plugin folder, or cannot be removed.
    """
    folder_name = _slug(plugin_id)
    if not folder_name or folder_name != plugin_id:
        raise PluginRefused("That is not a plugin id")

    base = Path(PLUGINS_BASE_PATH)
    folder = base / folder_name
    try:
        resolved = folder.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise PluginRefused(f"{plugin_id} is not installed") from exc

    if resolved.parent != base.resolve() or not resolved.is_dir():
        raise PluginRefused(f"{plugin_id} is not a plugin folder")

    try:
        shutil.rmtree(resolved)
    except OSError as exc:
        raise PluginRefused(f"Cannot remove {plugin_id}: {exc}") from exc

    _forget(base)
    log.info(f"Plugins: removed {plugin_id}")


def _forget(base: Path) -> None:
    """Drop the parsed shelf so the next read sees the new state."""
    with _CACHE_LOCK:
        _CACHE.pop(str(base), None)


def _parse_setting(raw: Any, plugin_id: str) -> PluginSettingSchema | None:
    """One field of a plugin's settings form, as the UI will render it.

    Args:
        raw: The field, as written.
        plugin_id: The owning plugin, for the log line.

    Returns:
        PluginSettingSchema | None: The field, or None when it is unusable.
    """
    if not isinstance(raw, dict):
        return None
    key = _slug(raw.get("key"))
    label = _text(raw.get("label"), MAX_LABEL_LENGTH)
    if not key or not label:
        log.warning(f"Plugins: {plugin_id} has a setting without a 'key' or 'label'")
        return None

    kind = raw.get("type", "text")
    if kind not in SETTING_TYPES:
        log.warning(f"Plugins: {plugin_id}.{key} has an unknown type {kind!r}")
        return None

    options: list[PluginSettingOptionSchema] = []
    if kind == "select":
        raw_options = raw.get("options")
        if not isinstance(raw_options, list) or not raw_options:
            log.warning(f"Plugins: {plugin_id}.{key} is a select with no options")
            return None
        for entry in raw_options[:MAX_SETTING_OPTIONS]:
            if not isinstance(entry, dict):
                continue
            value = _text(entry.get("value"), MAX_TEXT_LENGTH)
            if not value:
                continue
            options.append(
                PluginSettingOptionSchema(
                    value=value,
                    label=_text(entry.get("label"), MAX_LABEL_LENGTH) or value,
                )
            )
        if not options:
            log.warning(f"Plugins: {plugin_id}.{key} has no usable option")
            return None

    default = raw.get("default")
    if kind == "boolean":
        default = bool(default) if default is not None else False
    elif kind == "number":
        default = default if isinstance(default, (int, float)) else None
    else:
        default = _text(default, MAX_TEXT_LENGTH) if default is not None else None

    return PluginSettingSchema(
        key=key,
        label=label,
        type=kind,
        default=default,
        help=_text(raw.get("help"), MAX_TEXT_LENGTH),
        placeholder=_text(raw.get("placeholder"), MAX_TEXT_LENGTH),
        options=options,
        min=raw.get("min") if isinstance(raw.get("min"), (int, float)) else None,
        max=raw.get("max") if isinstance(raw.get("max"), (int, float)) else None,
        required=raw.get("required") is True,
    )


def plugin_settings(plugin: PluginSchema) -> dict[str, Any]:
    """The plugin's saved values, with the manifest's defaults filled in.

    A value the file no longer describes, or one of the wrong type, is dropped:
    the manifest is the shape, and a settings file outlives the version that
    wrote it.

    Args:
        plugin: The plugin as the shelf read it.

    Returns:
        dict[str, Any]: One value per setting the manifest declares.
    """
    saved = _read_settings(Path(PLUGINS_BASE_PATH) / plugin.id / SETTINGS_NAME)
    values: dict[str, Any] = {}
    for setting in plugin.settings:
        # No saved value, or one this version can't use: the manifest's default.
        if setting.key in saved and _value_fits(setting, saved[setting.key]):
            values[setting.key] = saved[setting.key]
        else:
            values[setting.key] = setting.default
    return values


def save_plugin_settings(
    plugin: PluginSchema, values: dict[str, Any]
) -> dict[str, Any]:
    """Validate values against the manifest and write them beside it.

    Args:
        plugin: The plugin the values belong to.
        values: What the form sent, keyed by setting key.

    Returns:
        dict[str, Any]: The values as they were stored.

    Raises:
        PluginRefused: A key the manifest doesn't declare, or a value of the
            wrong type, or the folder can't be written.
    """
    known = {setting.key: setting for setting in plugin.settings}
    stored: dict[str, Any] = {}
    for key, value in values.items():
        setting = known.get(key)
        if setting is None:
            raise PluginRefused(f"{plugin.name} has no setting called {key}")
        if not _value_fits(setting, value):
            raise PluginRefused(f"{setting.label} is not a valid {setting.type}")
        stored[key] = value

    # Settings the manifest declares but the form left out keep their default,
    # so a client that knows only half the fields cannot erase the rest.
    for setting in plugin.settings:
        if setting.key not in stored:
            stored[setting.key] = setting.default

    folder = Path(PLUGINS_BASE_PATH) / plugin.id
    path = folder / SETTINGS_NAME
    try:
        folder.mkdir(parents=True, exist_ok=True)
        tmp = folder / f".{SETTINGS_NAME}.tmp"
        tmp.write_text(
            json.dumps(stored, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        tmp.replace(path)
    except OSError as exc:
        raise PluginRefused(f"Cannot save {plugin.name}'s settings: {exc}") from exc
    log.info(f"Plugins: saved {len(stored)} settings for {plugin.id}")
    return stored


def _read_settings(path: Path) -> dict[str, Any]:
    """The settings file, or an empty mapping when it is missing or unreadable."""
    try:
        if path.stat().st_size > MAX_MANIFEST_BYTES:
            return {}
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError, ValueError:
        return {}
    return raw if isinstance(raw, dict) else {}


def _value_fits(setting: PluginSettingSchema, value: Any) -> bool:
    """Whether a value is one this setting can hold.

    Args:
        setting: The field the value is for.
        value: What was stored or sent.

    Returns:
        bool: True when the value matches the field's type.
    """
    if value is None:
        return not setting.required
    if setting.type == "boolean":
        return isinstance(value, bool)
    if setting.type == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return False
        if setting.min is not None and value < setting.min:
            return False
        return setting.max is None or value <= setting.max
    if setting.type == "select":
        return isinstance(value, str) and any(o.value == value for o in setting.options)
    if setting.type == "url":
        return isinstance(value, str) and (not value or _is_web_url(value))
    return isinstance(value, str) and len(value) <= MAX_TEXT_LENGTH


def store_plugins() -> list[StorePluginSchema]:
    """The curated index, as Settings, Plugins lists it.

    The index is a JSON file a repository maintains; a submission there is the
    only review a plugin gets, which is why installing from it is the same
    act as installing any other manifest.

    Returns:
        list[StorePluginSchema]: The plugins the store offers.

    Raises:
        PluginRefused: The index cannot be fetched or read.
    """
    url = os.environ.get("ROMM_PLUGIN_STORE", STORE_URL)
    raw = _fetch_json(url, MAX_STORE_BYTES, "the plugin store")
    entries = raw.get("plugins")
    if not isinstance(entries, list):
        raise PluginRefused("The plugin store's index lists no plugins")

    plugins: list[StorePluginSchema] = []
    for entry in entries[:MAX_STORE_PLUGINS]:
        if not isinstance(entry, dict):
            continue
        plugin_id = _slug(entry.get("id"))
        name = _text(entry.get("name"), MAX_TEXT_LENGTH)
        manifest_url = _text(entry.get("manifest_url"), MAX_URL_LENGTH)
        if (
            not plugin_id
            or not name
            or not manifest_url
            or not _is_web_url(manifest_url)
        ):
            continue
        tags = [
            _text(tag, MAX_LABEL_LENGTH)
            for tag in (entry.get("tags") or [])[:MAX_STORE_TAGS]
            if isinstance(tag, str)
        ]
        plugins.append(
            StorePluginSchema(
                id=plugin_id,
                name=name,
                version=_text(entry.get("version"), MAX_TEXT_LENGTH) or "0.0.0",
                description=_text(entry.get("description"), MAX_TEXT_LENGTH),
                author=_text(entry.get("author"), MAX_TEXT_LENGTH),
                homepage=_text(entry.get("homepage"), MAX_URL_LENGTH),
                manifest_url=manifest_url,
                tags=[tag for tag in tags if tag],
            )
        )
    return plugins


def install_from_store(plugin_id: str) -> PluginSchema:
    """Install the store's manifest for this id.

    Args:
        plugin_id: The id the store lists.

    Returns:
        PluginSchema: The installed plugin.

    Raises:
        PluginRefused: The store has no such plugin, or it won't install.
    """
    for entry in store_plugins():
        if entry.id == plugin_id:
            return install_plugin(url=entry.manifest_url)
    raise PluginRefused(f"The store has no plugin called {plugin_id}")


def _fetch_json(url: str, limit: int, what: str) -> dict[str, Any]:
    """Read a small JSON document over http(s).

    Args:
        url: Where it lives.
        limit: The largest body to accept.
        what: What the document is, for the refusal message.

    Returns:
        dict[str, Any]: The body.

    Raises:
        PluginRefused: The scheme, status, size or JSON is not acceptable.
    """
    parsed = urlsplit(url)
    if parsed.scheme not in WEB_SCHEMES or not parsed.netloc:
        raise PluginRefused(f"{what} must be an http or https URL")
    try:
        with httpx.stream("GET", url, timeout=10, follow_redirects=True) as response:
            if response.status_code != 200:
                raise PluginRefused(f"{what} answered {response.status_code}")
            body = b""
            for chunk in response.iter_bytes():
                body += chunk
                if len(body) > limit:
                    raise PluginRefused(f"{what} is larger than it should be")
    except PluginRefused:
        raise
    except httpx.HTTPError as exc:
        raise PluginRefused(f"Cannot fetch {what}: {exc}") from exc
    try:
        raw = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise PluginRefused(f"{what} is not JSON") from exc
    if not isinstance(raw, dict):
        raise PluginRefused(f"{what} is not a JSON object")
    return raw
