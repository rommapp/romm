# uv run python -m utils.update_hltb_api_url
"""
Utility script to update HowLongToBeat API URL by discovering the dynamic endpoint from the website
"""

import re
import sys
import time
from pathlib import Path

import httpx

from utils.context import create_httpx_client
from utils.hltb_search import (
    HLTB_BASE_URL,
    SESSION_MINT_SUFFIX,
    HLTBSession,
    base_headers,
    build_search_payload,
    parse_session,
    search_body,
    search_headers,
)

# Next.js lists every route it serves as a plain literal in _buildManifest.js.
BUILD_MANIFEST_REGEX = re.compile(
    r'src=["\'](?P<path>[^"\']*/_next/static/[^"\']+/_buildManifest\.js)["\']'
)
API_ROUTE_REGEX = re.compile(r'["\'](?P<route>/api/[^"\']*)["\']')

# A term with many well known hits, so an empty result means the route, not the term.
VALIDATION_SEARCH_TERM = "mario"


def fetch_build_manifest(client: httpx.Client, base_url: str) -> str | None:
    """Fetch the Next.js build manifest linked from the homepage."""
    headers = base_headers(base_url)
    homepage_url = f"{base_url}/"
    response = client.get(homepage_url, headers=headers, timeout=15)
    response.raise_for_status()
    print(f"Fetched homepage: {homepage_url}")

    match = BUILD_MANIFEST_REGEX.search(response.text)
    if not match:
        print("Could not locate the Next.js build manifest.", file=sys.stderr)
        return None

    manifest_url = str(httpx.URL(homepage_url).join(match.group("path")))
    print(f"Located build manifest: {manifest_url}")

    response = client.get(manifest_url, headers=headers, timeout=15)
    response.raise_for_status()
    print(f"Downloaded build manifest (size: {len(response.text)} chars)")

    return response.text


def candidate_search_routes(manifest: str) -> list[str]:
    """List the API routes that ship a session mint, most search-like first."""
    routes = list(dict.fromkeys(API_ROUTE_REGEX.findall(manifest)))

    # serves_game_search() is the real oracle, so this only narrows and orders.
    candidates = [
        route for route in routes if f"{route}{SESSION_MINT_SUFFIX}" in routes
    ]
    return sorted(candidates, key=lambda route: "search" not in route)


def _mint_session(
    client: httpx.Client, base_url: str, search_url: str
) -> HLTBSession | None:
    """Mint a session at the candidate's /init, or None if it does not issue one."""
    response = client.get(
        f"{search_url}{SESSION_MINT_SUFFIX}",
        params={"t": int(time.time())},
        headers=base_headers(base_url),
        timeout=15,
    )
    response.raise_for_status()

    return parse_session(response.json())


def _rejection_reason(
    client: httpx.Client, base_url: str, search_url: str
) -> str | None:
    try:
        session = _mint_session(client, base_url, search_url)
        if not session:
            return "/init issued no session"

        payload = build_search_payload(VALIDATION_SEARCH_TERM, "")
        response = client.post(
            search_url,
            json=search_body(payload, session),
            headers=search_headers(base_url, session),
            timeout=30,
        )
        response.raise_for_status()
        results = response.json().get("data")
    except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as e:
        return str(e)

    # The same shape search_games() reads.
    if not isinstance(results, list) or not results:
        return "search returned no results"

    if not all(
        isinstance(game, dict) and "game_id" in game and "game_name" in game
        for game in results
    ):
        return "results are not HLTB games"

    return None


def serves_game_search(client: httpx.Client, base_url: str, search_url: str) -> bool:
    """Check the candidate answers the search HLTBHandler sends, not just /init."""
    reason = _rejection_reason(client, base_url, search_url)
    if reason:
        print(f"Rejected {search_url}: {reason}")
        return False

    print(f"Confirmed {search_url} serves game search")
    return True


def discover_hltb_endpoint(base_url: str = HLTB_BASE_URL) -> str | None:
    """Discover the current HLTB search endpoint from the site's route table."""
    base_url = base_url.rstrip("/")
    try:
        with create_httpx_client() as client:
            manifest = fetch_build_manifest(client, base_url)
            if not manifest:
                return None

            candidates = candidate_search_routes(manifest)
            if not candidates:
                print("No API route offers a session mint.", file=sys.stderr)
                return None
            print(f"Candidate search routes: {', '.join(candidates)}")

            for route in candidates:
                search_url = f"{base_url}{route}"
                if serves_game_search(client, base_url, search_url):
                    print(f"Resolved HLTB search endpoint: {search_url}")
                    return search_url

            print("No candidate route served game search.", file=sys.stderr)
            return None
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        print(f"Error discovering HLTB endpoint: {e}", file=sys.stderr)
        return None


def main():
    """Main function to discover and update the HLTB API URL."""
    print("Starting HLTB API URL discovery...")

    search_url = discover_hltb_endpoint()

    if not search_url:
        print("Failed to discover HLTB API URL")
        sys.exit(1)

    # Write to the expected location
    fixture_path = (
        Path(__file__).parent.parent
        / "handler"
        / "metadata"
        / "fixtures"
        / "hltb_api_url"
    )

    try:
        with open(fixture_path, "w") as f:
            f.write(f"{search_url}\n")
        print(f"Successfully updated HLTB API URL to: {search_url}")
        print(f"Written to: {fixture_path}")
    except OSError as e:
        print(f"Error writing to fixture file: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
