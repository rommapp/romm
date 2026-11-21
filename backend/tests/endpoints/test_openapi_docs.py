"""Checks that the OpenAPI document describes every operation."""

from main import app

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
