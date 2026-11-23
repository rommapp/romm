from fastapi import FastAPI
from pydantic import BaseModel

from utils.openapi import publish_socket_payloads


class _Inner(BaseModel):
    value: int


class _Payload(BaseModel):
    name: str
    inner: _Inner


class _Route(BaseModel):
    ok: bool


def _app() -> FastAPI:
    app = FastAPI()

    @app.get("/route")
    def route() -> _Route:
        return _Route(ok=True)

    publish_socket_payloads(app, [_Payload])
    return app


def test_payload_and_its_nested_models_join_route_schemas():
    schemas = _app().openapi()["components"]["schemas"]

    assert "_Route" in schemas
    assert schemas["_Payload"]["properties"]["inner"] == {
        "$ref": "#/components/schemas/_Inner"
    }
    assert "_Inner" in schemas


def test_schema_is_built_once():
    app = _app()

    assert app.openapi() is app.openapi()


def test_app_without_routes_still_gets_the_payloads():
    app = FastAPI()
    publish_socket_payloads(app, [_Payload])

    assert "_Payload" in app.openapi()["components"]["schemas"]
