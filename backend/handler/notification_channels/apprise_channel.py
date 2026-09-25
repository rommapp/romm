"""Deliveries through Apprise, which reaches 100+ services from a URL built from their fields."""

import json
import logging
import re
from collections.abc import Mapping
from contextvars import ContextVar
from dataclasses import dataclass
from functools import cache
from typing import Any, Final, Literal
from urllib.parse import quote, urlencode, urlsplit, urlunsplit

from apprise import (
    Apprise,
    AppriseAsset,
    NotificationManager,
    NotifyBase,
    NotifyFormat,
    NotifyType,
)

from models.notification import NotificationLevel

from .messages import OutboundMessage

ADMINS_ONLY: Final = "Only admins can use Apprise channels"

# A service can ask for longer (?cto=, ?rto=), which would hold a worker.
CONNECT_TIMEOUT_SECONDS: Final = 10.0
READ_TIMEOUT_SECONDS: Final = 15.0

# Schemas that act on the machine running RomM instead of reaching a service.
LOCAL_SCHEMAS: Final = (
    "syslog",
    "windows",
    "macosx",
    "dbus",
    "gnome",
    "kde",
    "qt",
    "glib",
    "blink1",
)
# Options Apprise loads as a local file or a URL it fetches.
FILE_OPTIONS: Final = frozenset(
    {"template", "keyfile", "subfile", "pgppub", "pgpkey", "pgpprv"}
)
# Options every service shares that RomM sets itself or that don't apply here.
MANAGED_OPTIONS: Final = frozenset(
    {
        "cto",
        "rto",
        "retry",
        "wait",
        "redirect",
        "store",
        "optional",
        "overflow",
        "format",
        "emojis",
        "tz",
    }
)
# Services that post to any path on their host, which no token names.
FREE_PATH_SERVICES: Final = frozenset({"json", "xml", "form"})
# FCM reads its service account key from a path or URL it opens itself.
EXCLUDED_SERVICES: Final = frozenset({"fcm"})
# Fields that decide where a channel's secrets are sent.
DESTINATION_FIELDS: Final = frozenset({"schema", "host", "port", "smtp", "mode"})
# Tokens Apprise doesn't mark private although they are credentials.
_SECRET_NAME: Final = re.compile(r"token|key|secret|pass|webhook|auth|sid", re.I)
# Chat services turn these into pings of a whole server or a role.
_MENTIONS: Final = re.compile(r"@(everyone|here)\b|<[@!]")

NOTIFY_TYPES: Final[dict[str, NotifyType]] = {
    NotificationLevel.INFO: NotifyType.INFO,
    NotificationLevel.SUCCESS: NotifyType.SUCCESS,
    NotificationLevel.WARNING: NotifyType.WARNING,
    NotificationLevel.ERROR: NotifyType.FAILURE,
}

_ASSET: Final = AppriseAsset(
    app_id="RomM",
    app_desc="RomM",
    app_url="https://romm.app",
    # Nothing a plugin keeps (tokens, generated keys) is written to disk.
    storage_mode="memory",
    pgp_autogen=False,
    pem_autogen=False,
    http_redirects=False,
    secure_logging=True,
)

NotificationManager().disable(*LOCAL_SCHEMAS)

_PLACEHOLDER: Final = re.compile(r"{(\w+)}")
# A hostname, an IPv4 address or a bracketed IPv6 one.
_HOST: Final = re.compile(r"\[[0-9a-f:.]+\]|[\w.-]+", re.I)
# A token that is a URL path, which Apprise wants between slashes.
_PATH_TOKEN: Final = "path"

FieldType = Literal["string", "int", "float", "bool", "choice", "list"]
FieldValue = str | int | float | bool | list[str]

# The warnings Apprise logs during the send running in this context.
_warnings: ContextVar[list[str] | None] = ContextVar("apprise_warnings", default=None)


class _WarningCollector(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        collected = _warnings.get()
        if collected is not None:
            collected.append(record.getMessage())


# Warnings and up only: debug records carry the remote end's response body.
logging.getLogger("apprise").addHandler(_WarningCollector(logging.WARNING))


class AppriseError(RuntimeError):
    """The service refused the notification or could not be reached."""


@dataclass(frozen=True)
class AppriseField:
    key: str
    label: str
    type: FieldType
    required: bool
    private: bool
    # An option sent as a query argument rather than part of the URL itself.
    advanced: bool
    default: str | int | float | bool | None = None
    values: tuple[str | int, ...] | None = None
    min: float | None = None
    max: float | None = None
    # Separates a list's items in the URL.
    delimiter: str = ","
    # Singular tokens a template can take instead of this list.
    members: tuple[str, ...] = ()


@dataclass(frozen=True)
class AppriseService:
    id: str
    name: str
    setup_url: str | None
    schemas: tuple[str, ...]
    default_schema: str
    templates: tuple[str, ...]
    fields: tuple[AppriseField, ...]

    def field(self, key: str) -> AppriseField | None:
        return next((field for field in self.fields if field.key == key), None)


_FIELD_TYPES: Final[dict[str, FieldType]] = {
    "string": "string",
    "int": "int",
    "float": "float",
    "bool": "bool",
    "choice": "choice",
    "list": "list",
}


def _field_type(kind: str) -> FieldType | None:
    """Apprise's `choice:string` or `list:int` by the form control it needs."""
    return _FIELD_TYPES.get(kind.split(":", 1)[0])


def _field(
    key: str, meta: dict[str, Any], *, advanced: bool, required: bool = False
) -> AppriseField | None:
    field_type = _field_type(meta.get("type", "string"))
    if field_type is None:
        return None
    values = meta.get("values")
    private = bool(meta.get("private")) or (
        not advanced and field_type == "string" and bool(_SECRET_NAME.search(key))
    )
    return AppriseField(
        key=key,
        label=meta.get("name") or key,
        type=field_type,
        required=required,
        private=private,
        advanced=advanced,
        default=meta.get("default"),
        values=tuple(values) if values else None,
        min=meta.get("min"),
        max=meta.get("max"),
        delimiter=(meta.get("delim") or [","])[0],
        members=tuple(sorted(meta.get("group") or ())),
    )


def _service(entry: dict[str, Any]) -> AppriseService | None:
    details = entry["details"]
    tokens: dict[str, dict[str, Any]] = details["tokens"]
    templates = tuple(details["templates"])
    placeholders = [set(_PLACEHOLDER.findall(template)) for template in templates]
    protocols = [
        *(entry.get("protocols") or []),
        *(entry.get("secure_protocols") or []),
    ]
    if not protocols or not templates or protocols[0] in EXCLUDED_SERVICES:
        return None

    secure = entry.get("secure_protocols") or []
    default_schema = secure[0] if secure else protocols[0]
    members = {member for meta in tokens.values() for member in meta.get("group") or ()}
    fields: list[AppriseField] = []
    if len(protocols) > 1:
        fields.append(
            AppriseField(
                key="schema",
                label=tokens.get("schema", {}).get("name") or "Schema",
                type="choice",
                required=True,
                private=False,
                advanced=False,
                default=default_schema,
                values=tuple(protocols),
            )
        )
    for key, meta in tokens.items():
        if key == "schema" or key in members:
            continue
        spelled = {key, *(meta.get("group") or ())}
        # Alternative credentials are each required somewhere, so only what
        # every template needs is required.
        required = all(spelled & needed for needed in placeholders)
        field = _field(key, meta, advanced=False, required=required)
        if field:
            fields.append(field)

    if protocols[0] in FREE_PATH_SERVICES:
        # A webhook's path often carries its token.
        fields.append(
            AppriseField(
                key=_PATH_TOKEN,
                label="Path",
                type="string",
                required=False,
                private=True,
                advanced=False,
            )
        )

    shown = {field.key for field in fields}
    for key, meta in details["args"].items():
        if (
            "alias_of" in meta
            or key in shown
            or key in tokens
            or key in FILE_OPTIONS
            or key in MANAGED_OPTIONS
        ):
            continue
        field = _field(key, meta, advanced=True)
        if field:
            fields.append(field)

    return AppriseService(
        id=protocols[0],
        name=entry.get("service_name") or protocols[0],
        setup_url=entry.get("setup_url"),
        schemas=tuple(protocols),
        default_schema=default_schema,
        templates=templates,
        fields=tuple(fields),
    )


@cache
def services() -> tuple[AppriseService, ...]:
    """Every service Apprise can reach from here, by name."""
    # Apprise's own serializer, as its details hold sets; it answers False
    # when it can't serialize them.
    serialized = Apprise().json()
    if not isinstance(serialized, str):
        return ()
    found = (_service(entry) for entry in json.loads(serialized)["schemas"])
    return tuple(sorted((s for s in found if s), key=lambda s: s.name.lower()))


def find_service(service_id: str) -> AppriseService:
    """Raises:
    ValueError: RomM has no such Apprise service.
    """
    for service in services():
        if service.id == service_id:
            return service
    raise ValueError("Apprise has no such service")


def _blank(value: object) -> bool:
    return value is None or value == "" or value == []


def known_fields(
    service: AppriseService, fields: Mapping[str, FieldValue]
) -> dict[str, FieldValue]:
    """The fields the service takes that were filled in."""
    return {
        key: value
        for key, value in fields.items()
        if service.field(key) is not None and not _blank(value)
    }


def _scrub(text: str, service: AppriseService, fields: Mapping[str, FieldValue]) -> str:
    """The text with the channel's secrets hidden, as Apprise may quote them."""
    for field in service.fields:
        value = fields.get(field.key)
        if not field.private or _blank(value):
            continue
        for secret in value if isinstance(value, list) else [value]:
            secret = str(secret)
            for form in {secret, quote(secret, safe="")}:
                text = text.replace(form, "****")
    return text


def _text(field: AppriseField, value: FieldValue) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, list):
        return field.delimiter.join(str(item) for item in value)
    return str(value)


def _segment(key: str, value: FieldValue, field: AppriseField | None) -> str:
    """A token's value as it sits in the URL."""
    if key == "host":
        text = str(value).strip()
        if not _HOST.fullmatch(text):
            raise ValueError(f"{field.label if field else key} isn't a hostname")
        return text
    if key == _PATH_TOKEN:
        # Gotify's {host}{path}{token} needs the path between slashes.
        path = str(value).strip("/")
        return f"/{quote(path)}/" if path else "/"
    if isinstance(value, list):
        delimiter = field.delimiter if field else "/"
        return delimiter.join(quote(str(item), safe="") for item in value)
    return quote(str(value), safe="")


def _fill(
    service: AppriseService, template: str, tokens: dict[str, FieldValue]
) -> tuple[str, set[str]] | None:
    """The template with its tokens filled in and the tokens it took, or None
    when it needs one that wasn't given."""
    owners = {member: f.key for f in service.fields for member in f.members}
    filled, used = template, set()
    for key in _PLACEHOLDER.findall(template):
        if key == "schema":
            continue
        if key in tokens:
            text = _segment(key, tokens[key], service.field(key))
            used.add(key)
        else:
            # A singular token can come from its list when that holds one item.
            owner = owners.get(key)
            items = tokens.get(owner) if owner else None
            if owner is None or not isinstance(items, list) or len(items) != 1:
                return None
            text = _segment(key, items[0], None)
            used.add(owner)
        filled = filled.replace(f"{{{key}}}", text, 1)
    return filled, used


def build_url(service_id: str, fields: Mapping[str, FieldValue]) -> str:
    """The Apprise URL for a service's fields.

    Raises:
        ValueError: With a reason fit to show the user.
    """
    service = find_service(service_id)
    tokens: dict[str, FieldValue] = {}
    options: dict[str, str] = {}
    for key, value in fields.items():
        field = service.field(key)
        if field is None or key == "schema" or _blank(value):
            continue
        if field.advanced:
            options[key] = _text(field, value)
        else:
            tokens[key] = value
    schema = str(fields.get("schema") or service.default_schema)
    if schema not in service.schemas:
        raise ValueError(f"{service.name} doesn't take {schema}://")

    extra_path = (
        tokens.pop(_PATH_TOKEN, None) if service.id in FREE_PATH_SERVICES else None
    )

    fits = [
        filled
        for template in service.templates
        if (filled := _fill(service, template, tokens)) and filled[1] == set(tokens)
    ]
    if not fits:
        missing = [
            f.label
            for f in service.fields
            if f.required and f.key != "schema" and f.key not in tokens
        ]
        raise ValueError(
            f"{service.name} needs {', '.join(missing)}"
            if missing
            else f"{service.name} can't take these fields together"
        )

    url = fits[0][0].replace("{schema}", schema, 1)
    if extra_path:
        url += "/" + quote(str(extra_path).lstrip("/"))
    return f"{url}?{urlencode(options)}" if options else url


def _plugin(url: str) -> NotifyBase:
    """Raises:
    ValueError: With a reason fit to show the user.
    """
    try:
        plugin = Apprise.instantiate(url, asset=_ASSET, suppress_exceptions=False)
    except Exception as exc:  # noqa: BLE001 - a plugin says why it refused the URL
        raise ValueError(str(exc) or "Apprise can't use these fields") from exc
    if plugin is None:
        raise ValueError("Apprise can't use these fields")
    return plugin


def _checked_plugin(service: AppriseService, fields: Mapping[str, FieldValue]):
    """Raises:
    ValueError: With a reason fit to show the user, secrets hidden.
    """
    try:
        return _plugin(build_url(service.id, fields))
    except ValueError as exc:
        raise ValueError(_scrub(str(exc), service, fields)) from exc


def check(service_id: str, fields: Mapping[str, FieldValue]) -> dict[str, FieldValue]:
    """The fields to keep, once Apprise can deliver with them.

    Raises:
        ValueError: With a reason fit to show the user.
    """
    service = find_service(service_id)
    kept = known_fields(service, fields)
    _checked_plugin(service, kept)
    return kept


def describe(
    service_id: str, fields: Mapping[str, FieldValue]
) -> tuple[str | None, str]:
    """The service's name, and its URL with the secrets and options hidden."""
    try:
        service = find_service(service_id)
        plugin = _checked_plugin(service, fields)
    except ValueError:
        return None, ""
    scheme, netloc, path, _, _ = urlsplit(plugin.url(privacy=True))
    target = urlunsplit((scheme, netloc, path, "", ""))
    return service.name, _scrub(target, service, fields)


def split_fields(
    service_id: str, fields: Mapping[str, FieldValue]
) -> tuple[dict[str, FieldValue], list[str]]:
    """The fields that aren't secrets, for the owner's form, and which secrets are set."""
    try:
        service = find_service(service_id)
    except ValueError:
        return {}, []
    public: dict[str, FieldValue] = {}
    secrets: list[str] = []
    for field in service.fields:
        value = fields.get(field.key)
        if value is None or _blank(value):
            continue
        if field.private:
            secrets.append(field.key)
        else:
            public[field.key] = value
    return public, secrets


def merge_fields(
    service_id: str,
    stored: Mapping[str, FieldValue],
    given: Mapping[str, FieldValue],
) -> dict[str, FieldValue]:
    """The fields after an edit: a secret left out keeps its value, an empty one goes.

    Raises:
        ValueError: A secret would stay while the address it goes to changes.
    """
    service = find_service(service_id)
    merged = known_fields(service, given)
    kept = [
        field
        for field in service.fields
        if field.private and field.key not in given and field.key in stored
    ]
    moved = any(stored.get(key) != merged.get(key) for key in DESTINATION_FIELDS)
    if kept and moved:
        labels = ", ".join(field.label for field in kept)
        raise ValueError(
            f"Enter {labels} again for the new address, "
            f"or remove {'it' if len(kept) == 1 else 'them'}"
        )
    merged.update({field.key: stored[field.key] for field in kept})
    return merged


def _quiet(text: str) -> str:
    """The text with its mentions broken by a zero-width space, so they ping nobody."""
    return _MENTIONS.sub(lambda m: m.group(0)[0] + "\u200b" + m.group(0)[1:], text)


def _bounded(plugin: NotifyBase) -> NotifyBase:
    plugin.redirects = False
    # RQ retries a failed delivery on its own schedule.
    plugin.retry = 0
    plugin.socket_connect_timeout = min(
        plugin.socket_connect_timeout or CONNECT_TIMEOUT_SECONDS,
        CONNECT_TIMEOUT_SECONDS,
    )
    plugin.socket_read_timeout = min(
        plugin.socket_read_timeout or READ_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS
    )
    return plugin


def send(
    service_id: str, fields: Mapping[str, FieldValue], message: OutboundMessage
) -> None:
    """Deliver the message through Apprise; blocks until the service answers.

    Raises:
        ValueError: The fields no longer make a URL Apprise can use.
        AppriseError: The service refused it, or could not be reached.
    """
    service = find_service(service_id)
    plugin = _bounded(_checked_plugin(service, fields))
    apprise = Apprise(asset=_ASSET)
    apprise.add(plugin)
    body = "\n\n".join(part for part in (message.body, message.url) if part)

    collected: list[str] = []
    token = _warnings.set(collected)
    try:
        sent = apprise.notify(
            body=_quiet(body or message.title),
            title=_quiet(message.title),
            notify_type=NOTIFY_TYPES.get(message.notification.level, NotifyType.INFO),
            body_format=NotifyFormat.TEXT,
        )
    finally:
        _warnings.reset(token)

    if not sent:
        reason = " ".join(dict.fromkeys(collected))
        raise AppriseError(
            _scrub(reason, service, fields)
            or f"{plugin.service_name} did not take the notification"
        )
