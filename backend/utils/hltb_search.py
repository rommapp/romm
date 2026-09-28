"""The HowLongToBeat search wire contract, shared by the handler and the endpoint
discovery script."""

from pathlib import Path
from typing import Any, Final, NamedTuple

HLTB_BASE_URL: Final[str] = "https://howlongtobeat.com"

# The last discovered search URL, written by update_hltb_api_url and bundled.
HLTB_API_URL_FIXTURE: Final[Path] = (
    Path(__file__).parent.parent / "handler" / "metadata" / "fixtures" / "hltb_api_url"
)

# HLTB issues a session at the search route's own /init sibling.
SESSION_MINT_SUFFIX: Final[str] = "/init"

# The session token decodes to "<issued-at>::<public IP>|<user agent>.<hmac>",
# so logging it would put the host's public IP in any shared log or support bundle.
HLTB_SESSION_HEADERS: Final[frozenset[str]] = frozenset(
    {"x-auth-token", "x-hp-key", "x-hp-val"}
)


class HLTBSession(NamedTuple):
    token: str
    # The honeypot pair is optional, and is echoed back only when /init issues it.
    hp_key: str | None = None
    hp_val: str | None = None

    def honeypot(self) -> tuple[str, str] | None:
        """The (key, val) pair to echo back, or None when /init did not issue both."""
        if self.hp_key and self.hp_val:
            return self.hp_key, self.hp_val
        return None


def parse_session(data: object) -> HLTBSession | None:
    """Read a session out of an /init response, or None if it did not issue one."""
    if not isinstance(data, dict):
        return None

    token = data.get("token")
    if not token:
        return None

    return HLTBSession(token, data.get("hpKey"), data.get("hpVal"))


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
        # HLTB's own search is a same-origin POST, which browsers send with an Origin.
        "Origin": base_url,
        "x-auth-token": session.token,
    }
    if honeypot := session.honeypot():
        headers["x-hp-key"], headers["x-hp-val"] = honeypot
    return headers


def search_body(payload: dict[str, Any], session: HLTBSession) -> dict[str, Any]:
    honeypot = session.honeypot()
    if not honeypot:
        return payload
    # Some HLTB endpoints require the key:val in the payload. The key rotates with
    # the session, so copy the payload instead of accumulating stale keys.
    hp_key, hp_val = honeypot
    return {**payload, hp_key: hp_val}


def build_search_payload(search_term: str, platform_name: str) -> dict[str, Any]:
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
