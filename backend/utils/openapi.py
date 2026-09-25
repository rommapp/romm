from collections.abc import Sequence
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel
from pydantic.json_schema import models_json_schema


def publish_socket_payloads(app: FastAPI, models: Sequence[type[BaseModel]]) -> None:
    """Add Socket.IO payload models to the app's OpenAPI components.

    No route references them, so FastAPI would leave them out, and the
    frontend's generated types would lack the shapes its socket handlers read.
    """
    build_schema = app.openapi

    def openapi() -> dict[str, Any]:
        if app.openapi_schema is None:
            schema = build_schema()
            _, definitions = models_json_schema(
                [(model, "serialization") for model in models],
                ref_template="#/components/schemas/{model}",
            )
            components = schema.setdefault("components", {}).setdefault("schemas", {})
            components.update(definitions.get("$defs", {}))
        return app.openapi_schema

    app.openapi = openapi  # type: ignore[method-assign]
