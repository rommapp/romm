#!/usr/bin/env python3
"""Fill provider platform names into the static platform lists.

IGDB_CLIENT_ID and IGDB_CLIENT_SECRET refresh IGDB's abbreviation and alternative
name; SCREENSCRAPER_DEV_ID and SCREENSCRAPER_DEV_PASSWORD refresh ScreenScraper's
regional and common names. Neither needs Redis or a database. Run `trunk fmt` after.
"""

import ast
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parent.parent
IGDB_FILE = BACKEND / "adapters/services/igdb.py"
SS_FILE = BACKEND / "handler/metadata/ss_handler.py"

IGDB_NAME_KEYS = ("abbreviation", "alternative_name")
# IGDB caps a query at 500 results.
IGDB_MAX_RESULTS = 500
SS_NAME_KEYS = ("nom_eu", "nom_us", "nom_jp")

IGDBNames = dict[int, dict[str, Any]]
SSNames = dict[int, list[str]]

IGDB_LIST_RE = re.compile(
    r"^IGDB_PLATFORM_LIST: .*?^}$", flags=re.MULTILINE | re.DOTALL
)
IGDB_ENTRY_RE = re.compile(
    r"^(    UPS\.\w+: \{\n)(.*?)(^    \},\n)", flags=re.MULTILINE | re.DOTALL
)
IGDB_ID_RE = re.compile(r'^        "id": (\d+),$', flags=re.MULTILINE)
IGDB_NAME_LINE_RE = re.compile(
    rf'^        "({"|".join(IGDB_NAME_KEYS)})": .*\n', flags=re.MULTILINE
)

SS_LIST_RE = re.compile(
    r"^SCREENSAVER_PLATFORM_LIST: .*?^}$", flags=re.MULTILINE | re.DOTALL
)
SS_ENTRY_RE = re.compile(
    r"^    (UPS\.\w+): \{(.*?)\},\n", flags=re.MULTILINE | re.DOTALL
)
SS_ID_RE = re.compile(r'"id": (\w+)')
SS_NAME_RE = re.compile(r'"name": ("(?:[^"\\]|\\.)*")')
SS_CONSTANT_RE = re.compile(r"^(\w+_SS_ID): Final = (\d+)$", flags=re.MULTILINE)


def _request(
    url: str, data: bytes | None = None, headers: dict[str, str] | None = None
) -> Any:
    request = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.urlopen(request, timeout=60) as response:  # nosec B310
        return json.load(response)


def _rewrite_list(
    path: Path, list_re: re.Pattern[str], rewrite: Callable[[str], str]
) -> None:
    source = path.read_text()
    platform_list = list_re.search(source)
    if not platform_list:
        sys.exit(f"{list_re.pattern} not found in {path}")
    path.write_text(
        source[: platform_list.start()]
        + rewrite(platform_list.group())
        + source[platform_list.end() :]
    )


def fetch_igdb_names(client_id: str, client_secret: str, ids: list[int]) -> IGDBNames:
    token = _request(
        "https://id.twitch.tv/oauth2/token",
        urllib.parse.urlencode(
            {
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "client_credentials",
            }
        ).encode(),
    )["access_token"]
    query = (
        f"fields id,{','.join(IGDB_NAME_KEYS)};"
        f" where id = ({','.join(map(str, ids))});"
        f" limit {IGDB_MAX_RESULTS};"
    )
    platforms = _request(
        "https://api.igdb.com/v4/platforms",
        query.encode(),
        {"Client-ID": client_id, "Authorization": f"Bearer {token}"},
    )
    return {platform["id"]: platform for platform in platforms}


def rewrite_igdb_entry(entry: re.Match[str], names: IGDBNames) -> str:
    opening, body, closing = entry.groups()
    platform_id = int(IGDB_ID_RE.search(body).group(1))  # type: ignore[union-attr]
    if platform_id not in names:
        return entry.group()
    platform = names[platform_id]
    # Both keys sort before "category", so they open the entry.
    name_lines = "".join(
        f'        "{key}": {json.dumps(value.strip(), ensure_ascii=False)},\n'
        for key in IGDB_NAME_KEYS
        if (value := platform.get(key, "")).strip()
    )
    return opening + name_lines + IGDB_NAME_LINE_RE.sub("", body) + closing


def refresh_igdb(client_id: str, client_secret: str) -> None:
    platform_list = IGDB_LIST_RE.search(IGDB_FILE.read_text())
    if not platform_list:
        sys.exit(f"IGDB_PLATFORM_LIST not found in {IGDB_FILE}")
    ids = sorted({int(i) for i in IGDB_ID_RE.findall(platform_list.group())})
    if len(ids) > IGDB_MAX_RESULTS:
        sys.exit(f"{len(ids)} platforms need more than one IGDB query")

    names = fetch_igdb_names(client_id, client_secret, ids)
    _rewrite_list(
        IGDB_FILE,
        IGDB_LIST_RE,
        lambda text: IGDB_ENTRY_RE.sub(lambda m: rewrite_igdb_entry(m, names), text),
    )
    print(f"IGDB: updated {len(names)} of {len(ids)} platforms")


def ss_system_names(noms: dict[str, str]) -> list[str]:
    """A system's regional names, then its comma-separated common names, once each."""
    candidates = [noms.get(key, "") for key in SS_NAME_KEYS]
    candidates += noms.get("noms_commun", "").split(",")
    unique: dict[str, str] = {}
    for candidate in candidates:
        if candidate := candidate.strip():
            unique.setdefault(candidate.casefold(), candidate)
    return list(unique.values())


def fetch_ss_names(dev_id: str, dev_password: str) -> SSNames:
    query = urllib.parse.urlencode(
        {
            "devid": dev_id,
            "devpassword": dev_password,
            "softname": "romm",
            "output": "json",
        }
    )
    systems = _request(f"https://api.screenscraper.fr/api2/systemesListe.php?{query}")
    return {
        int(system["id"]): ss_system_names(system.get("noms", {}))
        for system in systems["response"]["systemes"]
    }


def rewrite_ss_list(text: str, constants: dict[str, str], names: SSNames) -> str:
    def entry_id(body: str) -> int:
        id_expr = SS_ID_RE.search(body).group(1)  # type: ignore[union-attr]
        return int(constants.get(id_expr, id_expr))

    # A system's names describe only one of the platforms filed under it.
    shared = {
        ss_id
        for ss_id, count in Counter(
            entry_id(m.group(2)) for m in SS_ENTRY_RE.finditer(text)
        ).items()
        if count > 1
    }

    def rewrite(entry: re.Match[str]) -> str:
        key, body = entry.groups()
        ss_id = entry_id(body)
        if ss_id not in names:
            return entry.group()
        id_expr = SS_ID_RE.search(body).group(1)  # type: ignore[union-attr]
        name = SS_NAME_RE.search(body).group(1)  # type: ignore[union-attr]
        own_name = ast.literal_eval(name).casefold()
        alternative_names = (
            []
            if ss_id in shared
            else [n for n in names[ss_id] if n.casefold() != own_name]
        )
        fields = f'"id": {id_expr}, "name": {name}'
        if alternative_names:
            fields += f', "alternative_names": {json.dumps(alternative_names, ensure_ascii=False)}'
        return f"    {key}: {{{fields}}},\n"

    return SS_ENTRY_RE.sub(rewrite, text)


def refresh_ss(dev_id: str, dev_password: str) -> None:
    constants = dict(SS_CONSTANT_RE.findall(SS_FILE.read_text()))
    names = fetch_ss_names(dev_id, dev_password)
    _rewrite_list(
        SS_FILE, SS_LIST_RE, lambda text: rewrite_ss_list(text, constants, names)
    )
    print(f"ScreenScraper: read names for {len(names)} systems")


def main() -> None:
    igdb = (os.environ.get("IGDB_CLIENT_ID"), os.environ.get("IGDB_CLIENT_SECRET"))
    ss = (
        os.environ.get("SCREENSCRAPER_DEV_ID"),
        os.environ.get("SCREENSCRAPER_DEV_PASSWORD"),
    )
    if not all(igdb) and not all(ss):
        sys.exit(
            "Set IGDB_CLIENT_ID and IGDB_CLIENT_SECRET, "
            "or SCREENSCRAPER_DEV_ID and SCREENSCRAPER_DEV_PASSWORD"
        )
    if igdb[0] and igdb[1]:
        refresh_igdb(igdb[0], igdb[1])
    if ss[0] and ss[1]:
        refresh_ss(ss[0], ss[1])


if __name__ == "__main__":
    main()
