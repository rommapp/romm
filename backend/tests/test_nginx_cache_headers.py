"""Guards the asset caching policy in the nginx template (issue #3890).

The Docker image's nginx serves the whole frontend. Assets fall into caching
classes and the template must sort each request into the right one:

  * Frozen forever (fingerprinted): content-hashed Vite bundles
    (``index-<hash>.js``) and library resources requested with a cache-busting
    query (covers ``?ts=``, manuals ``?v=``). The URL changes when the file
    does, so a cached copy is never stale.
  * Revalidating (stable URLs across image upgrades / re-scrapes): the bundled
    EmulatorJS/Ruffle runtimes, icons/fonts/logos, and the query-less resources
    (screenshots, RA badges, which reuse names like ``0.jpg`` and are
    overwritten in place).
  * ``no-cache`` (must always be fresh): ``index.html``, the service worker,
    and the root favicons/manifest.

The resources bucket splits on whether a recognized version param (``ts``/``v``)
is present, via the ``$resources_cache_control`` map (an unrelated query like
``?download=1`` must not freeze a stable file). Rather than grepping the
template for a string, this parses the ``location`` and ``map`` blocks and
replays nginx's matching for representative URLs, asserting the
``Cache-Control`` each resolves to.
"""

import re
from pathlib import Path

import pytest

NGINX_TEMPLATE = (
    Path(__file__).resolve().parents[2]
    / "docker"
    / "nginx"
    / "templates"
    / "default.conf.template"
)

IMMUTABLE_MAX_AGE = 31536000  # one year, in seconds
# Any revalidating cache must stay well under this so upgrades/re-scrapes show.
MAX_REVALIDATING_AGE = 86400  # one day, in seconds


def _read_block(text: str, start: int) -> tuple[str, int]:
    """Return (body, end) for a brace block whose opening ``{`` is at start-1,
    scanning to the matching ``}``. Blocks in this template do not nest."""
    depth = 1
    i = start
    while i < len(text) and depth:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        i += 1
    return text[start : i - 1], i


class Location:
    """A parsed nginx ``location``: modifier, match, and the Cache-Control it
    sets (a quoted literal, or a ``$variable`` resolved through a map)."""

    def __init__(self, modifier: str, match: str, body: str):
        self.modifier = modifier
        self.match = match
        cache = re.search(
            r'add_header\s+Cache-Control\s+(?:"([^"]*)"|(\$[A-Za-z0-9_]+))',
            body,
            re.IGNORECASE,
        )
        self.cache_control = (
            (cache.group(1) if cache.group(1) is not None else cache.group(2))
            if cache
            else None
        )

    @property
    def is_regex(self) -> bool:
        return self.modifier in ("~", "~*")

    @property
    def is_prefix(self) -> bool:
        return self.modifier in ("", "^~")


def _parse_locations(text: str) -> list[Location]:
    """Extract every ``location`` block, preserving file order (nginx evaluates
    regex locations in the order they appear)."""
    locations: list[Location] = []
    header = re.compile(r'location\s+(=|\^~|~\*|~)?\s*(?:"([^"]+)"|(\S+))\s*\{')
    for m in header.finditer(text):
        modifier = m.group(1) or ""
        match = m.group(2) if m.group(2) is not None else m.group(3)
        body, _ = _read_block(text, m.end())
        locations.append(Location(modifier, match, body))
    return locations


def _parse_maps(text: str) -> dict[str, tuple[str, dict[str, str]]]:
    """Parse ``map $in $out { key value; ... }`` -> {out: ($in, {key: value})}."""
    maps: dict[str, tuple[str, dict[str, str]]] = {}
    entry = re.compile(r'(?:"([^"]*)"|(\S+))\s+(?:"([^"]*)"|(\S+))\s*;')
    for m in re.finditer(r"map\s+(\$[A-Za-z0-9_]+)\s+\$([A-Za-z0-9_]+)\s*\{", text):
        input_var, output_var = m.group(1), m.group(2)
        body, _ = _read_block(text, m.end())
        entries: dict[str, str] = {}
        for e in entry.finditer(body):
            key = e.group(1) if e.group(1) is not None else e.group(2)
            value = e.group(3) if e.group(3) is not None else e.group(4)
            entries[key] = value
        maps[output_var] = (input_var, entries)
    return maps


def _input_value(input_var: str, url: str) -> str:
    """The nginx source a map keys on. Only ``$args`` is used here."""
    query = url.split("?", 1)[1] if "?" in url else ""
    if input_var == "$args":
        return query
    if input_var == "$is_args":
        return "?" if query else ""
    raise NotImplementedError(f"map input {input_var} not modelled")


def _eval_map(input_var: str, entries: dict[str, str], url: str) -> str | None:
    """Resolve an nginx ``map`` for ``url``, mirroring nginx precedence: exact
    keys first, then regex keys (``~``/``~*``) in order, else ``default``."""
    value = _input_value(input_var, url)
    for key, out in entries.items():
        if key != "default" and not key.startswith("~") and key == value:
            return out
    for key, out in entries.items():
        if key.startswith("~"):
            pattern = key[1:]
            flags = re.IGNORECASE if pattern.startswith("*") else 0
            if re.search(pattern.lstrip("*"), value, flags):
                return out
    return entries.get("default")


def _resolve(locations: list[Location], path: str) -> Location | None:
    """Replay nginx's location selection for ``path`` (query stripped): exact,
    then longest prefix, then first matching regex, else that prefix."""
    for loc in locations:
        if loc.modifier == "=" and loc.match == path:
            return loc

    best_prefix: Location | None = None
    for loc in locations:
        if loc.is_prefix and path.startswith(loc.match):
            if best_prefix is None or len(loc.match) > len(best_prefix.match):
                best_prefix = loc

    if best_prefix is not None and best_prefix.modifier == "^~":
        return best_prefix

    for loc in locations:
        if loc.is_regex:
            flags = re.IGNORECASE if loc.modifier == "~*" else 0
            if re.search(loc.match, path, flags):
                return loc

    return best_prefix


@pytest.fixture(scope="module")
def config() -> tuple[list[Location], dict[str, tuple[str, dict[str, str]]]]:
    text = NGINX_TEMPLATE.read_text()
    return _parse_locations(text), _parse_maps(text)


def _cache_control_for(config, url: str) -> str | None:
    locations, maps = config
    loc = _resolve(locations, url.split("?", 1)[0])
    assert loc is not None, f"no location matched {url}"
    cc = loc.cache_control
    if cc is not None and cc.startswith("$"):
        input_var, entries = maps[cc[1:]]
        cc = _eval_map(input_var, entries, url)
    return cc


# Fingerprinted -> safe to cache immutably forever. Library resources qualify
# only when they carry a cache-busting query (covers ?ts=, manuals ?v=).
IMMUTABLE_URLS = [
    "/assets/index-C-Cea5tF.js",
    "/assets/index-C-Cea5tF.css",
    "/assets/EmulatorJS--ZSfrbCp.js",  # hashed vite chunk with hyphens in name
    "/assets/emulatorjs-logotype-COnXko2R.svg",
    "/assets/inter-latin-Ckm5tF12.woff2",
    "/assets/romm/resources/roms/1/1/cover/small.png?ts=2026-01-01T00:00:00",
    "/assets/romm/resources/roms/1/1/cover/big.png?ts=1700000000",
    "/assets/romm/resources/roms/1/1/manual/1.pdf?v=1700000000",
]

# Stable URLs that must revalidate so an upgrade / re-scrape is picked up. This
# includes query-less resources: screenshots and RA badges reuse fixed names
# and are overwritten in place, so they are NOT safe to freeze.
REVALIDATING_URLS = [
    "/assets/emulatorjs/data/loader.js",  # bundled EmulatorJS runtime
    "/assets/emulatorjs/data/cores/snes9x-wasm.data",
    "/assets/ruffle/ruffle.js",
    "/assets/scrappers/ss.png",
    "/assets/platforms/default.ico",
    "/assets/isotipo.png",  # non-hashed file directly under /assets
    "/assets/patcherjs/patcherjs.png",
    "/assets/romm/resources/roms/1/1/screenshots/0.jpg",  # overwritten on re-scrape
    "/assets/romm/resources/roms/1/1/screenshots/1.jpg",
    "/assets/romm/resources/roms/1/1/ra/badges/12345.png",  # RA badge, no query
    # An unrelated query must NOT be mistaken for a version bust and frozen.
    "/assets/romm/resources/roms/1/1/screenshots/0.jpg?download=1",
]

# Served from ``location /`` (not /assets): index.html, the service worker and
# the favicons/manifest all keep stable names, so they must revalidate rather
# than be frozen. A stale index.html could point at purged, hashed bundles.
ROOT_REVALIDATING_URLS = [
    "/",
    "/index.html",
    "/library",  # SPA route -> index.html
    "/favicon.ico",
    "/favicon.svg",
    "/site.webmanifest",
    "/manifest.webmanifest",
    "/sw.js",
    "/apple-touch-icon.png",
]


@pytest.mark.parametrize("url", IMMUTABLE_URLS)
def test_fingerprinted_assets_are_immutable(config, url):
    cc = _cache_control_for(config, url)
    assert cc is not None, f"{url} has no Cache-Control"
    assert "immutable" in cc, f"{url} should be immutable, got: {cc!r}"
    max_age = re.search(r"max-age=(\d+)", cc)
    assert (
        max_age and int(max_age.group(1)) == IMMUTABLE_MAX_AGE
    ), f"{url} should cache for a year, got: {cc!r}"


@pytest.mark.parametrize("url", REVALIDATING_URLS)
def test_non_fingerprinted_assets_revalidate(config, url):
    cc = _cache_control_for(config, url)
    assert cc is not None, f"{url} should still be cacheable, got no Cache-Control"
    assert (
        "immutable" not in cc
    ), f"{url} keeps a stable URL across upgrades and must not be immutable: {cc!r}"
    assert (
        "must-revalidate" in cc
    ), f"{url} must revalidate so upgrades/re-scrapes propagate, got: {cc!r}"
    max_age = re.search(r"max-age=(\d+)", cc)
    assert (
        max_age and int(max_age.group(1)) <= MAX_REVALIDATING_AGE
    ), f"{url} cache window is too long to catch an upgrade: {cc!r}"


def test_resources_freeze_only_when_cache_busted(config):
    # Same resource tree: only a recognized version param (ts/v) freezes a
    # resource. A stable name with no query, or with an unrelated query, must
    # revalidate. This is why the resources bucket can't be a blanket immutable
    # rule, and why it keys on the param name rather than on "any query".
    cover = _cache_control_for(
        config, "/assets/romm/resources/roms/1/1/cover/small.png?ts=123"
    )
    screenshot = _cache_control_for(
        config, "/assets/romm/resources/roms/1/1/screenshots/0.jpg"
    )
    unrelated = _cache_control_for(
        config, "/assets/romm/resources/roms/1/1/screenshots/0.jpg?download=1"
    )
    assert cover is not None and screenshot is not None and unrelated is not None
    assert "immutable" in cover, f"cover should freeze, got: {cover!r}"
    assert (
        "immutable" not in screenshot and "must-revalidate" in screenshot
    ), f"queryless screenshot must revalidate, got: {screenshot!r}"
    assert (
        "immutable" not in unrelated and "must-revalidate" in unrelated
    ), f"unrelated ?download= must not freeze, got: {unrelated!r}"


@pytest.mark.parametrize("url", ROOT_REVALIDATING_URLS)
def test_root_files_revalidate(config, url):
    cc = _cache_control_for(config, url)
    assert cc is not None, f"{url} should carry a revalidating Cache-Control"
    assert "immutable" not in cc, f"{url} must not be immutable, got: {cc!r}"
    assert (
        "no-cache" in cc or "must-revalidate" in cc
    ), f"{url} must revalidate so deploys/updates propagate, got: {cc!r}"
