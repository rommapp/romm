"""Checks that the OpenAPI document describes every parameter, operation and schema field."""

from typing import Any

import pytest
from main import app

HTTP_METHODS = ("get", "post", "put", "patch", "delete", "head")

Operation = tuple[str, str, dict[str, Any]]


def _is_documented(node: dict[str, Any], schemas: dict[str, Any]) -> bool:
    """Whether `node`, or the schema it points at, has a description."""
    if (node.get("description") or "").strip():
        return True
    ref = node.get("$ref")
    if ref is None:
        return False
    return _is_documented(schemas[ref.split("/")[-1]], schemas)


def _referenced_names(node: Any) -> set[str]:
    """Every schema name `node` points at, at any depth."""
    if isinstance(node, dict):
        names = {node["$ref"].split("/")[-1]} if "$ref" in node else set()
        for value in node.values():
            names |= _referenced_names(value)
        return names
    if isinstance(node, list):
        return set().union(*(_referenced_names(item) for item in node))
    return set()


def _reachable_schemas(roots: set[str], schemas: dict[str, Any]) -> set[str]:
    reached: set[str] = set()
    pending = set(roots)
    while pending:
        name = pending.pop()
        reached.add(name)
        pending |= _referenced_names(schemas[name]) - reached
    return reached


@pytest.fixture(scope="module")
def spec() -> dict[str, Any]:
    return app.openapi()


@pytest.fixture(scope="module")
def operations(spec: dict[str, Any]) -> list[Operation]:
    """The operations under `/api`."""
    return [
        (method.upper(), path, operation)
        for path, item in spec["paths"].items()
        if path.startswith("/api/")
        for method, operation in item.items()
        if method in HTTP_METHODS
    ]


def _assert_none(problems: list[str], what: str) -> None:
    assert not problems, f"{len(problems)} {what} without a description:\n" + "\n".join(
        problems
    )


def test_every_parameter_has_a_description(operations: list[Operation]):
    # Arrange
    problems: list[str] = []

    # Act
    for method, path, operation in operations:
        for parameter in operation.get("parameters", []):
            if not (parameter.get("description") or "").strip():
                problems.append(
                    f"{method} {path}: {parameter['in']} `{parameter['name']}`"
                )

    # Assert
    _assert_none(problems, "parameters")


def test_every_operation_has_a_description(operations: list[Operation]):
    # Arrange / Act
    problems = [
        f"{method} {path}"
        for method, path, operation in operations
        if not (operation.get("description") or "").strip()
    ]

    # Assert
    _assert_none(problems, "operations")


# A schema with any described field must have all of them; untouched ones are skipped.
def test_every_started_schema_is_fully_documented(
    spec: dict[str, Any], operations: list[Operation]
):
    # Arrange
    schemas: dict[str, Any] = spec["components"]["schemas"]
    roots: set[str] = set()
    for _, _, operation in operations:
        roots |= _referenced_names(operation.get("requestBody", {}))
        roots |= _referenced_names(operation.get("responses", {}))

    # Act
    problems: list[str] = []
    for name in sorted(_reachable_schemas(roots, schemas)):
        properties = schemas[name].get("properties", {})
        documented = [_is_documented(node, schemas) for node in properties.values()]
        if any(documented) and not all(documented):
            problems += [
                f"{name}.{field}"
                for field, node in properties.items()
                if not _is_documented(node, schemas)
            ]

    # Assert
    _assert_none(problems, "schema fields in partly documented schemas")
