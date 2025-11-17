# uv run python -m utils.update_hltb_api_url
"""
Utility script to update HowLongToBeat API URL by discovering the dynamic endpoint from the website
"""

import re
import sys
from pathlib import Path

import httpx

# Precompiled regexes for better performance
APP_JS_REGEX = re.compile(
    r'src=["\'](?P<path>\/_next\/static\/chunks\/pages\/_app[^"\']+\.js)["\']'
)
APP_JS_FALLBACK_REGEX = re.compile(r'src=["\'](?P<path>[^"\']*_app[^"\']+\.js)["\']')
ENDPOINT_TOKEN_REGEX = re.compile(
    r'/api/(?P<endpoint>[a-zA-Z0-9_-]+)/["\']\.concat\(["\'](?P<part1>[0-9a-zA-Z]+)["\']\)\.concat\(["\'](?P<part2>[0-9a-zA-Z]+)["\']\)'
)


def fetch_hltb_app_script(base_url: str = "https://howlongtobeat.com") -> str | None:
    """Fetch the HLTB app script from the site."""
    try:
        with httpx.Client() as client:
            # 1) Fetch homepage HTML
            homepage_url = f"{base_url}/"
            resp = client.get(homepage_url, timeout=15)
            resp.raise_for_status()
            html = resp.text
            print(f"Fetched homepage: {homepage_url}")

            # 2) Find the Next.js _app chunk (typical pattern: "/_next/static/chunks/pages/_app-<hash>.js")
            app_js_match = APP_JS_REGEX.search(html)
            if not app_js_match:
                # Fallback: any script path containing "_app" ending with .js
                app_js_match = APP_JS_FALLBACK_REGEX.search(html)
            if not app_js_match:
                print("Could not locate HLTB _app JS chunk.")
                return None
            app_js_path = app_js_match.group("path")
            print(f"Located app JS path: {app_js_path}")

            app_js_url = (
                app_js_path
                if app_js_path.startswith("http")
                else f"{base_url.rstrip('/')}/{app_js_path.lstrip('/')}"
            )
            print(f"Constructed app JS URL: {app_js_url}")

            # 3) Download the _app JS chunk
            js_resp = client.get(app_js_url, timeout=15)
            js_resp.raise_for_status()
            js_code = js_resp.text
            print(f"Downloaded app JS chunk (size: {len(js_code)} chars)")

            return js_code
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        print(f"Error fetching HLTB app script: {e}", file=sys.stderr)
        return None


def discover_hltb_endpoint(base_url: str = "https://howlongtobeat.com") -> str | None:
    """Discover the current HLTB API endpoint by fetching and parsing the app script."""
    try:
        # 1) Fetch the app script
        js_code = fetch_hltb_app_script(base_url)

        if not js_code:
            print("Could not fetch HLTB app script; using default search endpoint")
            return None

        # 2) Extract the endpoint and tokens from the app script
        token_match = ENDPOINT_TOKEN_REGEX.search(js_code)
        if not token_match:
            print(
                "Could not extract HLTB endpoint and tokens from _app JS; using default search endpoint"
            )
            return None

        endpoint = token_match.group("endpoint")
        part1 = token_match.group("part1")
        part2 = token_match.group("part2")

        print(f"Extracted endpoint: {endpoint}")
        print(f"Extracted token part1: {part1}")
        print(f"Extracted token part2: {part2}")

        # 3) Build the search URL
        search_url = f"{base_url}/api/{endpoint}/{part1}{part2}"
        print(f"Resolved HLTB search endpoint: {search_url}")

        return search_url
    except (IOError, OSError) as e:
        print(
            f"Unexpected error discovering HLTB endpoint from site: {e}",
            file=sys.stderr,
        )
        return None


def main():
    """Main function to discover and update the HLTB API URL."""
    print("Starting HLTB API URL discovery...")

    search_url = discover_hltb_endpoint()

    if not search_url:
        print("Failed to discover HLTB API URL")
        sys.exit(1)
        return

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
            f.write(search_url)
        print(f"Successfully updated HLTB API URL to: {search_url}")
        print(f"Written to: {fixture_path}")
    except Exception as e:
        print(f"Error writing to fixture file: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
