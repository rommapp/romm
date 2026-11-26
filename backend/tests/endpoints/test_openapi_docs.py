"""Checks that the OpenAPI document describes every operation."""

from main import app
from tools.route_errors import UNREADABLE_STATUS, stale, undocumented

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
    # Act
    gaps = undocumented(app.routes)

    # Assert
    assert not gaps, (
        "These routes raise or return statuses their `responses=` does not describe."
        " Document each one, or mark code whose errors never reach the client with"
        f" `# route-errors: ignore`. A status of {UNREADABLE_STATUS} is one the"
        " analyzer cannot read: use a literal status, or declare the statuses the"
        " line can take with `# route-errors: raises <codes>`:\n"
        + "\n".join(f"{route} {codes}" for route, codes in gaps.items())
    )


def test_documented_statuses_are_raised():
    # Act
    gaps = stale(app.routes)

    # Assert
    assert not gaps, (
        "These routes document statuses they cannot raise. Remove each entry, or,"
        " if the route does raise it in a way the analyzer cannot follow, declare"
        " it on the line that raises it with `# route-errors: raises <codes>`:\n"
        + "\n".join(f"{route} {codes}" for route, codes in gaps.items())
    )
