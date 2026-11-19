"""What the OpenAPI document tells a reader about the documented endpoints.

Reads `app.openapi()`, the document Swagger, ReDoc and the generated frontend
types come from, so it checks what readers see: inherited fields, parameters
FastAPI derives and fields documented through attribute docstrings included.

A parameter, schema field or operation counts as documented when it carries a
non-blank description. Two rules keep the check passing while the rest of the
API is documented:

- Every parameter and operation of a router in `DOCUMENTED_ROUTERS` must be
  documented. Add a router there once its parameters and operations are done.
- A schema with any documented field must have all of them documented. A schema
  nobody has started is skipped.

A failure counts the gaps per group, then lists some.
"""

from collections import Counter
from typing import Any

import pytest
from main import app

HTTP_METHODS = ("get", "post", "put", "patch", "delete")
GROUPS_SHOWN = 30
LINES_SHOWN = 20

# The first path segment after `/api` for each router held to the rule.
DOCUMENTED_ROUTERS = frozenset(
    {
        "roms",
        "platforms",
        "collections",
        "users",
        "saves",
        "states",
        "screenshots",
        "channels",
        "snapshots",
        "streaming",
        "devices",
        "client-tokens",
        "play-sessions",
        "search",
        "music",
        "memory-cards",
        "firmware",
        "sync",
        "config",
        "feeds",
        "notifications",
        "notification-channels",
        "permissions",
        "tasks",
        "activity",
        "heartbeat",
        "export",
        "audit-events",
        "recommendations",
        "stats",
        "logs",
        "netplay",
        "auth",
        "login",
        "logout",
        "token",
        "oauth",
        "setup",
        "forgot-password",
        "reset-password",
    }
)

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
        if name in reached:
            continue
        reached.add(name)
        pending |= _referenced_names(schemas[name]) - reached
    return reached


def _router(path: str) -> str:
    """The first segment after `/api`, which is the router that owns the path."""
    segments = [part for part in path.split("/") if part]
    return segments[1] if len(segments) > 1 and segments[0] == "api" else path


@pytest.fixture(scope="module")
def spec() -> dict[str, Any]:
    return app.openapi()


@pytest.fixture(scope="module")
def operations(spec: dict[str, Any]) -> list[Operation]:
    """The operations of the routers in `DOCUMENTED_ROUTERS`."""
    return [
        (method.upper(), path, operation)
        for path, item in spec["paths"].items()
        if _router(path) in DOCUMENTED_ROUTERS
        for method, operation in item.items()
        if method in HTTP_METHODS
    ]


def _assert_none(problems: list[tuple[str, str]], what: str) -> None:
    """Fail with the gaps counted per group, then the first few in full."""
    per_group = Counter(group for group, _ in problems).most_common(GROUPS_SHOWN)
    counts = ", ".join(f"{group} {count}" for group, count in per_group)
    lines = "\n".join(f"  {line}" for _, line in problems[:LINES_SHOWN])
    assert not problems, (
        f"{len(problems)} {what} without a description.\n"
        f"By group: {counts}\n{lines}"
    )


def test_documented_routers_exist(spec: dict[str, Any]):
    # Arrange
    present = {_router(path) for path in spec["paths"]}

    # Act
    missing = sorted(DOCUMENTED_ROUTERS - present)

    # Assert
    assert missing == [], f"DOCUMENTED_ROUTERS names routers with no paths: {missing}"


def test_every_parameter_has_a_description(operations: list[Operation]):
    # Arrange
    problems: list[tuple[str, str]] = []

    # Act
    for method, path, operation in operations:
        for parameter in operation.get("parameters", []):
            if not (parameter.get("description") or "").strip():
                problems.append(
                    (
                        _router(path),
                        f"{method} {path}: {parameter['in']} `{parameter['name']}`",
                    )
                )

    # Assert
    _assert_none(problems, "parameters")


def test_every_operation_has_a_description(operations: list[Operation]):
    # Arrange / Act
    problems = [
        (_router(path), f"{method} {path}")
        for method, path, operation in operations
        if not (operation.get("description") or "").strip()
    ]

    # Assert
    _assert_none(problems, "operations")


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
    problems: list[tuple[str, str]] = []
    for name in sorted(_reachable_schemas(roots, schemas)):
        properties = schemas[name].get("properties", {})
        documented = [_is_documented(node, schemas) for node in properties.values()]
        if any(documented) and not all(documented):
            problems += [
                (name, f"{name}.{field}")
                for field, node in properties.items()
                if not _is_documented(node, schemas)
            ]

    # Assert
    _assert_none(problems, "schema fields in partly documented schemas")
