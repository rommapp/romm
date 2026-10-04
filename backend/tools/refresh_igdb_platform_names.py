#!/usr/bin/env python3
"""Fill IGDB's abbreviation and alternative name into `IGDB_PLATFORM_LIST`.

Reads IGDB_CLIENT_ID and IGDB_CLIENT_SECRET from the environment, asks IGDB
for every listed platform's names, and rewrites adapters/services/igdb.py in
place. Entries IGDB has no value for keep neither key. Run `trunk fmt` after.
"""

import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

IGDB_FILE = Path(__file__).resolve().parent.parent / "adapters/services/igdb.py"
NAME_KEYS = ("abbreviation", "alternative_name")
# IGDB caps a query at 500 results.
PAGE_SIZE = 500

PlatformNames = dict[int, dict[str, Any]]

LIST_RE = re.compile(r"^IGDB_PLATFORM_LIST: .*?^}$", flags=re.MULTILINE | re.DOTALL)
ENTRY_RE = re.compile(
    r"^(    UPS\.\w+: \{\n)(.*?)(^    \},\n)", flags=re.MULTILINE | re.DOTALL
)
ID_RE = re.compile(r'^        "id": (\d+),$', flags=re.MULTILINE)
NAME_LINE_RE = re.compile(
    rf'^        "({"|".join(NAME_KEYS)})": .*\n', flags=re.MULTILINE
)


def _post(url: str, data: bytes, headers: dict[str, str]) -> Any:
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=30) as response:  # nosec B310
        return json.load(response)


def fetch_names(client_id: str, client_secret: str, ids: list[int]) -> PlatformNames:
    token = _post(
        "https://id.twitch.tv/oauth2/token",
        urllib.parse.urlencode(
            {
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "client_credentials",
            }
        ).encode(),
        {},
    )["access_token"]
    headers = {"Client-ID": client_id, "Authorization": f"Bearer {token}"}

    names: PlatformNames = {}
    for start in range(0, len(ids), PAGE_SIZE):
        page = ids[start : start + PAGE_SIZE]
        query = (
            f"fields id,{','.join(NAME_KEYS)};"
            f" where id = ({','.join(map(str, page))});"
            f" limit {PAGE_SIZE};"
        )
        for platform in _post(
            "https://api.igdb.com/v4/platforms", query.encode(), headers
        ):
            names[platform["id"]] = platform
    return names


def rewrite_entry(entry: re.Match[str], names: PlatformNames) -> str:
    opening, body, closing = entry.groups()
    platform_id = int(ID_RE.search(body).group(1))  # type: ignore[union-attr]
    platform = names.get(platform_id, {})
    # Both keys sort before "category", so they open the entry.
    name_lines = "".join(
        f'        "{key}": {json.dumps(value.strip(), ensure_ascii=False)},\n'
        for key in NAME_KEYS
        if (value := platform.get(key, "")).strip()
    )
    return opening + name_lines + NAME_LINE_RE.sub("", body) + closing


def main() -> None:
    client_id = os.environ.get("IGDB_CLIENT_ID")
    client_secret = os.environ.get("IGDB_CLIENT_SECRET")
    if not client_id or not client_secret:
        sys.exit("Set IGDB_CLIENT_ID and IGDB_CLIENT_SECRET")

    source = IGDB_FILE.read_text()
    platform_list = LIST_RE.search(source)
    if not platform_list:
        sys.exit(f"IGDB_PLATFORM_LIST not found in {IGDB_FILE}")

    ids = sorted({int(i) for i in ID_RE.findall(platform_list.group())})
    names = fetch_names(client_id, client_secret, ids)
    new_list = ENTRY_RE.sub(lambda m: rewrite_entry(m, names), platform_list.group())
    IGDB_FILE.write_text(
        source[: platform_list.start()] + new_list + source[platform_list.end() :]
    )
    print(f"Updated {len(names)} of {len(ids)} platforms in {IGDB_FILE}")


if __name__ == "__main__":
    main()
