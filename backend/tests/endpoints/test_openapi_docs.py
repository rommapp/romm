"""Checks that the OpenAPI document describes every operation."""

import json
from pathlib import Path

from main import app
from tools.route_errors import undocumented

# The statuses routes raised without documenting them when this check was added.
# Entries may be removed from it, never added.
BASELINE = Path(__file__).with_name("route_error_baseline.json")

HTTP_METHODS = ("get", "post", "put", "patch", "delete", "head")


def test_every_operation_has_a_description():
    # Arrange
    spec = app.openapi()

    # Act
    problems = [
        f"{method.upper()} {path}"
        for path, item in spec["paths"].items()
        if path.startswith("/api/")
        for method, operation in item.items()
        if method in HTTP_METHODS and not (operation.get("description") or "").strip()
    ]

    # Assert
    assert (
        not problems
    ), f"{len(problems)} operations without a description:\n" + "\n".join(problems)


def test_raised_statuses_are_documented():
    # Arrange
    baseline = json.loads(BASELINE.read_text())

    # Act
    gaps = undocumented(app.routes)

    # Assert
    new = {
        route: sorted(set(codes) - set(baseline.get(route, [])))
        for route, codes in gaps.items()
        if set(codes) - set(baseline.get(route, []))
    }
    fixed = {
        route: sorted(set(codes) - set(gaps.get(route, [])))
        for route, codes in baseline.items()
        if set(codes) - set(gaps.get(route, []))
    }
    assert not new, (
        "These routes raise statuses their `responses=` does not describe:\n"
        + "\n".join(f"{route} {codes}" for route, codes in new.items())
    )
    assert not fixed, (
        f"These statuses are documented now; remove them from {BASELINE.name}:\n"
        + "\n".join(f"{route} {codes}" for route, codes in fixed.items())
    )
