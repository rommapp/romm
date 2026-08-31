"""The HowLongToBeat search wire contract, shared by the handler and the endpoint
discovery script."""

from typing import Final, NamedTuple

from utils import get_version

HLTB_BASE_URL: Final[str] = "https://howlongtobeat.com"

# HLTB issues a session at the search route's own /init sibling.
SESSION_MINT_SUFFIX: Final[str] = "/init"

# The session token decodes to "<issued-at>::<public IP>|<user agent>|<key>|<hmac>",
# so logging it would put the host's public IP in any shared log or support bundle.
HLTB_SESSION_HEADERS: Final[frozenset[str]] = frozenset(
    {"x-auth-token", "x-hp-key", "x-hp-val"}
)


class HLTBSession(NamedTuple):
    token: str
    hp_key: str
    hp_val: str


def parse_session(data: dict) -> HLTBSession | None:
    """Read a session out of an /init response, or None if it did not issue one."""
    token, hp_key, hp_val = (data.get(field) for field in ("token", "hpKey", "hpVal"))
    if not (token and hp_key and hp_val):
        return None

    return HLTBSession(token, hp_key, hp_val)


def base_headers(base_url: str) -> dict[str, str]:
    # HLTB binds a session to the user agent that requested it, so every call
    # has to send the same one.
    return {"Referer": base_url, "User-Agent": f"RomM/{get_version()}"}


def search_headers(base_url: str, session: HLTBSession) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        **base_headers(base_url),
        "x-auth-token": session.token,
        "x-hp-key": session.hp_key,
        "x-hp-val": session.hp_val,
    }


def search_body(payload: dict, session: HLTBSession) -> dict:
    # Some HLTB endpoints require the key:val in the payload. The key rotates with
    # the session, so copy the payload instead of accumulating stale keys.
    return {**payload, session.hp_key: session.hp_val}


def build_search_payload(search_term: str, platform_name: str) -> dict:
    return {
        "searchType": "games",
        "searchTerms": search_term.split(" "),
        "searchPage": 1,
        "size": 20,
        "searchOptions": {
            "games": {
                "userId": 0,
                "platform": platform_name,
                "sortCategory": "popular",
                "rangeCategory": "main",
                "rangeTime": {"min": None, "max": None},
                "gameplay": {
                    "perspective": "",
                    "flow": "",
                    "genre": "",
                    "difficulty": "",
                },
                "rangeYear": {"min": "", "max": ""},
                "modifier": "",
            },
            "users": {"sortCategory": "postcount"},
            "lists": {"sortCategory": "follows"},
            "filter": "",
            "sort": 0,
            "randomizer": 0,
        },
        "useCache": True,
    }
