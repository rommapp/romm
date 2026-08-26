# uv run python -m utils.update_hltb_api_url
"""
Utility script to update HowLongToBeat API URL by discovering the dynamic endpoint from the website
"""

import re
import sys
import time
from pathlib import Path

import httpx

from utils import get_version
from utils.context import create_httpx_client

BASE_URL = "https://howlongtobeat.com"

# Next.js lists every route it serves as a plain literal in _buildManifest.js, so
# discovery does not depend on how the app bundle happens to be built or minified.
BUILD_MANIFEST_REGEX = re.compile(
    r'src=["\'](?P<path>[^"\']*/_next/static/[^"\']+/_buildManifest\.js)["\']'
)
API_ROUTE_REGEX = re.compile(r'["\'](?P<route>/api/[^"\']*)["\']')

# HLTBHandler mints its session at f"{search_url}/init", so the search endpoint is
# the route the manifest pairs with an /init sibling.
SESSION_MINT_SUFFIX = "/init"
SESSION_FIELDS = ("token", "hpKey", "hpVal")


def _absolute_url(base_url: str, path: str) -> str:
    if path.startswith("http"):
        return path
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _base_headers(base_url: str) -> dict[str, str]:
    return {"Referer": base_url, "User-Agent": f"RomM/{get_version()}"}


def fetch_build_manifest(client: httpx.Client, base_url: str) -> str | None:
    """Fetch the Next.js build manifest linked from the homepage."""
    homepage_url = f"{base_url.rstrip('/')}/"
    response = client.get(homepage_url, headers=_base_headers(base_url), timeout=15)
    response.raise_for_status()
    print(f"Fetched homepage: {homepage_url}")

    match = BUILD_MANIFEST_REGEX.search(response.text)
    if not match:
        print("Could not locate the Next.js build manifest.", file=sys.stderr)
        return None

    manifest_url = _absolute_url(base_url, match.group("path"))
    print(f"Located build manifest: {manifest_url}")

    response = client.get(manifest_url, headers=_base_headers(base_url), timeout=15)
    response.raise_for_status()
    print(f"Downloaded build manifest (size: {len(response.text)} chars)")

    return response.text


def candidate_search_routes(manifest: str) -> list[str]:
    """List the API routes that ship a session mint, most search-like first."""
    routes = set(API_ROUTE_REGEX.findall(manifest))
    candidates = [
        route for route in routes if f"{route}{SESSION_MINT_SUFFIX}" in routes
    ]

    # Only an ordering hint, since every candidate is confirmed against the live API.
    return sorted(candidates, key=lambda route: ("search" not in route, route))


def mints_a_session(client: httpx.Client, base_url: str, search_url: str) -> bool:
    """Check that the endpoint issues the session HLTBHandler needs to search."""
    try:
        response = client.get(
            f"{search_url}{SESSION_MINT_SUFFIX}",
            params={"t": int(time.time())},
            headers=_base_headers(base_url),
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
    except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as e:
        print(f"Rejected {search_url}: {e}")
        return False

    if missing := [field for field in SESSION_FIELDS if not data.get(field)]:
        print(f"Rejected {search_url}: session is missing {', '.join(missing)}")
        return False

    print(f"Confirmed {search_url} mints a session")
    return True


def discover_hltb_endpoint(base_url: str = BASE_URL) -> str | None:
    """Discover the current HLTB search endpoint from the site's route table."""
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
                search_url = f"{base_url.rstrip('/')}{route}"
                if mints_a_session(client, base_url, search_url):
                    print(f"Resolved HLTB search endpoint: {search_url}")
                    return search_url

            print("No candidate route minted a session.", file=sys.stderr)
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
