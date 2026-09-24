"""The HowLongToBeat search wire contract, shared by the handler and the endpoint
discovery script."""

from typing import Final, NamedTuple

HLTB_BASE_URL: Final[str] = "https://howlongtobeat.com"

# HLTB issues a session at the search route's own /init sibling.
SESSION_MINT_SUFFIX: Final[str] = "/init"

# The session token decodes to "<issued-at>::<public IP>|<user agent>.<hmac>",
# so logging it would put the host's public IP in any shared log or support bundle.
HLTB_SESSION_HEADERS: Final[frozenset[str]] = frozenset(
    {"x-auth-token", "x-hp-key", "x-hp-val"}
)


class HLTBSession(NamedTuple):
    token: str
    # HLTB no longer issues this honeypot pair, but older /init responses carried it.
    hp_key: str | None = None
    hp_val: str | None = None


def parse_session(data: dict) -> HLTBSession | None:
    """Read a session out of an /init response, or None if it did not issue one."""
    token = data.get("token")
    if not token:
        return None

    hp_key, hp_val = data.get("hpKey"), data.get("hpVal")
    if hp_key and hp_val:
        return HLTBSession(token, hp_key, hp_val)

    return HLTBSession(token)


# HLTB's firewall rejects tool-style "Name/version" agents with a 403, so send a
# browser's. The session is bound to it, so every call has to send the same one.
HLTB_USER_AGENT: Final[str] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)


def base_headers(base_url: str) -> dict[str, str]:
    return {"Referer": base_url, "User-Agent": HLTB_USER_AGENT}


def search_headers(base_url: str, session: HLTBSession) -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        **base_headers(base_url),
        "x-auth-token": session.token,
    }
    if session.hp_key and session.hp_val:
        headers["x-hp-key"] = session.hp_key
        headers["x-hp-val"] = session.hp_val
    return headers


def search_body(payload: dict, session: HLTBSession) -> dict:
    if not (session.hp_key and session.hp_val):
        return payload
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
