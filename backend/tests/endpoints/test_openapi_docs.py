"""Checks that the OpenAPI document describes every operation."""

from main import app
from tools.route_errors import undocumented

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
        "These routes raise statuses their `responses=` does not describe. Document"
        " each one, or mark code whose errors never reach the client with"
        " `# route-errors: ignore`:\n"
        + "\n".join(f"{route} {codes}" for route, codes in gaps.items())
    )
