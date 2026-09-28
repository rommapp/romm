"""Deliveries through Apprise, which reaches 100+ services from a URL built from their fields."""

import json
import logging
import re
from collections.abc import Mapping
from contextvars import ContextVar
from dataclasses import dataclass
from functools import cache, cached_property
from typing import Any, Final, Literal, cast, get_args
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlsplit, urlunsplit

from apprise import (
    Apprise,
    AppriseAsset,
    NotificationManager,
    NotifyBase,
    NotifyFormat,
    NotifyType,
)
from apprise.utils.parse import parse_bool

from logger.logger import log
from models.notification import NotificationLevel

from .messages import OutboundMessage
from .webhook import ERROR_DETAIL_CHARS

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
# Options every service shares that are set here or don't apply.
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
# Where Apprise's setup guides live, one page per service.
WIKI_PAGE: Final = "https://github.com/caronc/apprise/wiki/Notify_{}"
# Services Apprise reads a URL of their own for (a Discord webhook's), whose
# native URL only covers a corner of what they do, so they keep their fields.
FIELD_SERVICES: Final = frozenset({"matrix", "lametric", "46elks", "wechat"})
# Where a URL points and whom it signs in as.
_URL_PARTS: Final = frozenset(
    {"schema", "host", "port", "user", "password", "path", "fullpath"}
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

# What a service shows as the sender's picture, such as Discord's avatar; it
# fetches it itself, so it has to be public.
ROMM_ICON_URL: Final = (
    "https://raw.githubusercontent.com/rommapp/romm/master/"
    "frontend/public/android-chrome-512x512.png"
)

_ASSET: Final = AppriseAsset(
    app_id="RomM",
    app_desc="RomM",
    app_url="https://romm.app",
    image_url_mask=ROMM_ICON_URL,
    image_url_logo=ROMM_ICON_URL,
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

# What Apprise logs about the send running in this context: its warnings, and
# the start of a refusal's reply, which says why (Discord's "Invalid Form Body").
_collected: ContextVar[list[str] | None] = ContextVar("apprise_log", default=None)
_REPLY: Final = "Response Details:"


class _Collector(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        collected = _collected.get()
        if record.levelno >= logging.WARNING:
            if collected is None:
                # No send reports it, so it goes to the server log.
                log.warning(f"Apprise: {record.getMessage()}")
            else:
                collected.append(record.getMessage())
        elif collected is not None and str(record.msg).startswith(_REPLY):
            reply = record.getMessage().removeprefix(_REPLY).strip()
            # Apprise logs the body as a bytes repr, b'...'.
            if reply[:2] in ("b'", 'b"'):
                reply = reply[2:-1]
            if reply:
                collected.append(f"Reply: {reply[:ERROR_DETAIL_CHARS]}")


_apprise_log = logging.getLogger("apprise")
# Down to debug, where the replies are, and past the server log: a send's
# failure is logged once, as the delivery's error.
_apprise_log.setLevel(logging.DEBUG)
_apprise_log.propagate = False
_apprise_log.addHandler(_Collector())


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
    # The fields the URL a service gives out (a Discord webhook's) fills in,
    # when it's set up from that URL; empty for a service without one.
    url_fields: tuple[str, ...] = ()

    @cached_property
    def _by_key(self) -> dict[str, AppriseField]:
        return {field.key: field for field in self.fields}

    @cached_property
    def owners(self) -> dict[str, AppriseField]:
        """The list each singular token belongs to."""
        return {member: field for field in self.fields for member in field.members}

    @cached_property
    def patterns(self) -> tuple[re.Pattern[str], ...]:
        """Each template as a pattern for the URL Apprise writes, fullest first."""
        ordered = sorted(
            self.templates, key=lambda t: len(_PLACEHOLDER.findall(t)), reverse=True
        )
        return tuple(_template_pattern(self, template) for template in ordered)

    @cached_property
    def secrets(self) -> frozenset[str]:
        return frozenset(field.key for field in self.fields if field.private)

    def field(self, key: str) -> AppriseField | None:
        return self._by_key.get(key)


def _setup_url(url: str | None) -> str | None:
    """The service's guide on Apprise's wiki, when Apprise points at appriseit.com."""
    parts = urlsplit(url or "")
    if parts.hostname != "appriseit.com":
        return url
    slug = parts.path.rstrip("/").rsplit("/", 1)[-1]
    return WIKI_PAGE.format(slug) if slug else None


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

    plugin = NotificationManager()[protocols[0]]
    native = (
        protocols[0] not in FIELD_SERVICES
        and plugin.parse_native_url is not NotifyBase.parse_native_url
    )
    # Such a URL holds what the service needs, where and whom it signs in as;
    # what it lacks (a Discord bot name) stays a field.
    url_fields = tuple(
        field.key
        for field in fields
        if native
        and not field.advanced
        and (field.required or field.private or field.key in _URL_PARTS)
    )
    return AppriseService(
        url_fields=url_fields,
        id=protocols[0],
        name=entry.get("service_name") or protocols[0],
        setup_url=_setup_url(entry.get("setup_url")),
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


# What each kind of template token matches in the URL Apprise writes.
_TOKEN_PATTERNS: Final = {
    "schema": r"[a-z0-9+.-]+",
    "host": _HOST.pattern,
    "port": r"\d+",
    "user": r"[^/:@?#]+",
    _PATH_TOKEN: r"/(?:[^?#]*/)?",
}


def _token_pattern(service: AppriseService, key: str) -> str:
    if key in _TOKEN_PATTERNS:
        return _TOKEN_PATTERNS[key]
    field = service.field(key)
    return r".+" if field is not None and field.type == "list" else r"[^/@?#]+"


def _template_pattern(service: AppriseService, template: str) -> re.Pattern[str]:
    template = template.rstrip("/")
    pattern, end = "", 0
    for match in _PLACEHOLDER.finditer(template):
        key = match.group(1)
        pattern += re.escape(template[end : match.start()])
        pattern += f"(?P<{key}>{_token_pattern(service, key)})"
        end = match.end()
    return re.compile(pattern + re.escape(template[end:]), re.I)


def _read(field: AppriseField, text: str, quoted: bool) -> FieldValue | None:
    """A value as it sits in the URL, back in the field's type."""
    if field.type == "list":
        items = re.split(rf"[{re.escape(field.delimiter)},\s]+", text)
        return [unquote(item) if quoted else item for item in items if item]
    text = unquote(text) if quoted else text
    if field.type == "bool":
        return cast(FieldValue | None, parse_bool(text))
    if field.type in ("int", "float"):
        try:
            return int(text) if field.type == "int" else float(text)
        except ValueError:
            return None
    return text


def fields_from_url(url: str) -> tuple[AppriseService, dict[str, FieldValue]]:
    """The service and fields behind an Apprise URL or a service's own, such as
    a Discord webhook's.

    Raises:
        ValueError: With a reason fit to show the user.
    """
    url = url.strip()
    if not url or any(char.isspace() for char in url):
        raise ValueError("Paste one URL, without spaces")
    pasted = urlsplit(url)
    if pasted.scheme.lower() in EXCLUDED_SCHEMAS:
        raise ValueError("RomM doesn't offer that service")
    if {key.lower() for key, _ in parse_qsl(pasted.query)} & FILE_OPTIONS:
        raise ValueError("RomM doesn't take the options that read local files")
    try:
        plugin = Apprise.instantiate(url, asset=_ASSET, suppress_exceptions=False)
    except Exception as exc:  # noqa: BLE001 - a plugin says why it refused the URL
        raise ValueError(str(exc) or "Apprise can't read this URL") from exc
    if plugin is None:
        raise ValueError("Apprise can't read this URL")

    parts = urlsplit(plugin.url(privacy=False))
    service = next((s for s in services() if parts.scheme in s.schemas), None)
    if service is None:
        raise ValueError("RomM doesn't offer that service")

    fields: dict[str, FieldValue] = {}
    base = f"{parts.scheme}://{parts.netloc}{parts.path}".rstrip("/")
    if service.id in FREE_PATH_SERVICES:
        fields[_PATH_TOKEN] = unquote(parts.path.strip("/"))
        base = f"{parts.scheme}://{parts.netloc}"
    match = next((m for p in service.patterns if (m := p.fullmatch(base))), None)
    if match is None:
        raise ValueError(f"RomM can't read the {service.name} fields from this URL")

    for key, text in match.groupdict().items():
        field = service.owners.get(key) or service.field(key)
        if field is None or key == "schema" or not text:
            continue
        if (value := _read(field, text, quoted=True)) is not None:
            fields[field.key] = value
    for key, text in parse_qsl(parts.query, keep_blank_values=True):
        field = service.field(key)
        if field is None or not field.advanced:
            continue
        if (value := _read(field, text, quoted=False)) is not None:
            fields[key] = value
    if len(service.schemas) > 1:
        fields["schema"] = parts.scheme
    fields = known_fields(service, fields)
    # The fields must make the same URL again, or a token was misread.
    if _address(_plugin(service, fields).url(privacy=False)) != _address(
        plugin.url(privacy=False)
    ):
        raise ValueError(f"RomM can't read the {service.name} fields from this URL")
    return service, fields


def _address(url: str) -> tuple[str, str, str]:
    """A URL's scheme, authority and path, as Apprise writes it."""
    parts = urlsplit(url)
    return parts.scheme.lower(), parts.netloc, unquote(parts.path).rstrip("/")


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
    token = _collected.set(collected)
    try:
        sent = apprise.notify(
            body=_defuse_mentions(message.text),
            title=_defuse_mentions(message.title),
            notify_type=NOTIFY_TYPES.get(message.notification.level, NotifyType.INFO),
            body_format=NotifyFormat.TEXT,
        )
    finally:
        _collected.reset(token)

    if not sent:
        reason = " ".join(dict.fromkeys(collected))
        raise AppriseError(
            _scrub(reason, service, fields)
            or f"{plugin.service_name} did not take the notification"
        )
