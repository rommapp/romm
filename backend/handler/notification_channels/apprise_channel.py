"""Deliveries through Apprise, which reaches 100+ services from a URL built from their fields."""

import json
import logging
import re
from collections.abc import Mapping
from contextvars import ContextVar
from dataclasses import dataclass
from functools import cache, cached_property
from typing import Any, Final, Literal, get_args
from urllib.parse import quote, urlencode, urlsplit, urlunsplit

from apprise import Apprise, AppriseAsset, NotifyBase, NotifyFormat, NotifyType

from models.notification import NotificationLevel

from .messages import OutboundMessage

ADMINS_ONLY: Final = "Only admins can use Apprise channels"

# A service can ask for longer (?cto=, ?rto=), which would hold a worker.
CONNECT_TIMEOUT_SECONDS: Final = 10.0
READ_TIMEOUT_SECONDS: Final = 15.0

# Schemas that act on the machine running RomM instead of reaching a service,
# and FCM, which opens its key file from a path or URL itself.
EXCLUDED_SCHEMAS: Final = frozenset(
    {
        "syslog",
        "windows",
        "macosx",
        "dbus",
        "gnome",
        "kde",
        "qt",
        "glib",
        "blink1",
        "fcm",
    }
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

    @cached_property
    def _by_key(self) -> dict[str, AppriseField]:
        return {field.key: field for field in self.fields}

    @cached_property
    def owners(self) -> dict[str, AppriseField]:
        """The list each singular token belongs to."""
        return {member: field for field in self.fields for member in field.members}

    @cached_property
    def secrets(self) -> frozenset[str]:
        return frozenset(field.key for field in self.fields if field.private)

    def field(self, key: str) -> AppriseField | None:
        return self._by_key.get(key)


def _field(
    key: str, meta: dict[str, Any], *, advanced: bool, required: bool = False
) -> AppriseField | None:
    # Apprise's `choice:string` or `list:int`, by the form control it needs.
    kind = meta.get("type", "string").split(":", 1)[0]
    if kind not in get_args(FieldType):
        return None
    values = meta.get("values")
    private = bool(meta.get("private")) or (
        not advanced and kind == "string" and bool(_SECRET_NAME.search(key))
    )
    return AppriseField(
        key=key,
        label=meta.get("name") or key,
        type=kind,
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
    if not protocols or not templates or EXCLUDED_SCHEMAS & set(protocols):
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


@cache
def _services_by_id() -> dict[str, AppriseService]:
    return {service.id: service for service in services()}


def find_service(service_id: str) -> AppriseService:
    """Raises:
    ValueError: RomM has no such Apprise service.
    """
    service = _services_by_id().get(service_id)
    if service is None:
        raise ValueError("Apprise has no such service")
    return service


def _blank(value: object) -> bool:
    return value is None or value == "" or value == []


def known_fields(
    service: AppriseService, fields: Mapping[str, FieldValue]
) -> dict[str, FieldValue]:
    """The fields the service takes that were filled in, defaults left out."""
    return {
        key: value
        for key, value in fields.items()
        if (field := service.field(key)) is not None
        and not _blank(value)
        and value != field.default
    }


def _scrub(text: str, service: AppriseService, fields: Mapping[str, FieldValue]) -> str:
    """The text with the channel's secrets hidden, as Apprise may quote them."""
    for key in service.secrets:
        value = fields.get(key)
        if value is None or _blank(value):
            continue
        for secret in value if isinstance(value, list) else [value]:
            for form in {str(secret), quote(str(secret), safe="")}:
                text = text.replace(form, "****")
    return text


def _text(field: AppriseField, value: FieldValue) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, list):
        return field.delimiter.join(str(item) for item in value)
    return str(value)


def _segment(field: AppriseField, value: FieldValue) -> str:
    """A token's value as it sits in the URL."""
    if field.key == "host":
        text = str(value).strip()
        if not _HOST.fullmatch(text):
            raise ValueError(f"{field.label} isn't a hostname")
        return text
    if field.key == _PATH_TOKEN:
        # Gotify's {host}{path}{token} needs the path between slashes.
        path = str(value).strip("/")
        return f"/{quote(path)}/" if path else "/"
    if isinstance(value, list):
        return field.delimiter.join(quote(str(item), safe="") for item in value)
    return quote(str(value), safe="")


def _fill(
    service: AppriseService, template: str, tokens: dict[str, FieldValue]
) -> tuple[str, set[str]] | None:
    """The template with its tokens filled in and the tokens it took, or None
    when it needs one that wasn't given."""
    filled, used = template, set()
    for key in _PLACEHOLDER.findall(template):
        field = service.field(key)
        if field is not None and key in tokens:
            text = _segment(field, tokens[key])
            used.add(key)
        elif (owner := service.owners.get(key)) is not None:
            # A singular token can come from its list when that holds one item.
            items = tokens.get(owner.key)
            if not isinstance(items, list) or len(items) != 1:
                return None
            text = quote(str(items[0]), safe="")
            used.add(owner.key)
        elif key == "schema":
            continue
        else:
            return None
        filled = filled.replace(f"{{{key}}}", text, 1)
    return filled, used


def build_url(service: AppriseService, fields: Mapping[str, FieldValue]) -> str:
    """The Apprise URL for a service's fields.

    Raises:
        ValueError: With a reason fit to show the user.
    """
    tokens: dict[str, FieldValue] = {}
    options: dict[str, str] = {}
    for key, value in known_fields(service, fields).items():
        field = service.field(key)
        if field is None or key == "schema":
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
    fit = next(
        (
            filled
            for template in service.templates
            if (filled := _fill(service, template, tokens)) and filled[1] == set(tokens)
        ),
        None,
    )
    if fit is None:
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

    url = fit[0].replace("{schema}", schema, 1)
    if extra_path:
        url += "/" + quote(str(extra_path).lstrip("/"))
    return f"{url}?{urlencode(options)}" if options else url


def _plugin(service: AppriseService, fields: Mapping[str, FieldValue]) -> NotifyBase:
    """Raises:
    ValueError: With a reason fit to show the user, secrets hidden.
    """
    try:
        plugin = Apprise.instantiate(
            build_url(service, fields), asset=_ASSET, suppress_exceptions=False
        )
    except Exception as exc:  # noqa: BLE001 - a plugin says why it refused the URL
        reason = str(exc) or "Apprise can't use these fields"
        raise ValueError(_scrub(reason, service, fields)) from exc
    if plugin is None:
        raise ValueError("Apprise can't use these fields")
    return plugin


def checked_fields(
    service_id: str, fields: Mapping[str, FieldValue]
) -> dict[str, FieldValue]:
    """The fields to keep, once Apprise can deliver with them.

    Raises:
        ValueError: With a reason fit to show the user.
    """
    service = find_service(service_id)
    kept = known_fields(service, fields)
    _plugin(service, kept)
    return kept


def describe(
    service_id: str, fields: Mapping[str, FieldValue]
) -> tuple[str | None, str]:
    """The service's name, and its URL with the secrets and options hidden."""
    try:
        service = find_service(service_id)
        plugin = _plugin(service, fields)
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
    kept = known_fields(service, fields)
    public = {k: v for k, v in kept.items() if k not in service.secrets}
    return public, [key for key in kept if key in service.secrets]


def _destination(service: AppriseService, fields: Mapping[str, FieldValue]) -> Any:
    """Where the fields send to, as Apprise tells its URLs apart, or None."""
    try:
        return _plugin(service, fields).url_identifier or None
    except ValueError:
        return None


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
    kept = {
        key: value
        for key, value in stored.items()
        if key in service.secrets and key not in given
    }
    if kept:
        secrets = {k: v for k, v in stored.items() if k in service.secrets}
        before = {k: v for k, v in stored.items() if k not in service.secrets}
        after = {k: v for k, v in merged.items() if k not in service.secrets}
        # The same secrets on both sides, so only a new address counts.
        was = _destination(service, {**before, **secrets})
        now = _destination(service, {**after, **secrets})
        moved = was != now if was is not None and now is not None else before != after
        if moved:
            labels = ", ".join(
                field.label for field in service.fields if field.key in kept
            )
            raise ValueError(
                f"Enter {labels} again for the new address, "
                f"or remove {'it' if len(kept) == 1 else 'them'}"
            )
    return {**merged, **kept}


def _defuse_mentions(text: str) -> str:
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
    plugin = _bounded(_plugin(service, fields))
    apprise = Apprise(asset=_ASSET)
    apprise.add(plugin)

    collected: list[str] = []
    token = _warnings.set(collected)
    try:
        sent = apprise.notify(
            body=_defuse_mentions(message.text),
            title=_defuse_mentions(message.title),
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
