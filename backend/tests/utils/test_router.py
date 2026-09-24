import itertools
from typing import Annotated, Any

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field, create_model

from utils.router import APIRouter, as_query_dependency


@pytest.mark.parametrize(
    "method, route_path",
    itertools.product(
        ("get", "post", "put", "delete", "patch"),
        ("/test", "/test/"),
    ),
)
def test_route_path_with_trailing_slash(method, route_path):
    router = APIRouter()

    @router.get(route_path)
    @router.post(route_path)
    @router.put(route_path)
    @router.delete(route_path)
    @router.patch(route_path)
    def test_route(request: Request):
        return {"test": "test"}

    assert test_route(Request({"type": "http", "method": method, "url": "/test"})) == {
        "test": "test"
    }
    assert test_route(Request({"type": "http", "method": method, "url": "/test/"})) == {
        "test": "test"
    }


class Filters(BaseModel):
    name: Annotated[str | None, Field(description="A name.")] = None
    page: Annotated[int, Field(ge=1)] = 1


class TestAsQueryDependency:
    @staticmethod
    def _schema() -> list[dict]:
        """OpenAPI parameters of a route taking the model and one plain param."""
        router = APIRouter()

        @router.get("/things")
        def route(
            filters: Annotated[Filters, Depends(as_query_dependency(Filters))],
            order_by: str = "name",
        ):
            return filters

        app = FastAPI()
        app.include_router(router)
        return app.openapi()["paths"]["/things"]["get"]["parameters"]

    def test_fields_stay_flat_alongside_another_query_parameter(self):
        """The reason this helper exists: `Annotated[Model, Query()]` collapses
        to one `$ref` parameter as soon as the route takes anything else."""
        assert {param["name"] for param in self._schema()} == {
            "name",
            "page",
            "order_by",
        }

    def test_field_metadata_reaches_the_parameter(self):
        page = next(p for p in self._schema() if p["name"] == "page")

        assert page["schema"]["minimum"] == 1
        assert page["schema"]["default"] == 1

    def test_the_route_binds_the_fields_back_into_the_model(self):
        router = APIRouter()

        @router.get("/things")
        def route(
            filters: Annotated[Filters, Depends(as_query_dependency(Filters))],
        ):
            return {"name": filters.name, "page": filters.page}

        app = FastAPI()
        app.include_router(router)

        assert TestClient(app).get("/things?name=zelda&page=3").json() == {
            "name": "zelda",
            "page": 3,
        }

    @pytest.mark.parametrize(
        "annotation",
        [
            Annotated[list[str], Field(default_factory=list)],
            Annotated[str, Field("x", alias="other")],
        ],
        ids=["default_factory", "alias"],
    )
    def test_it_refuses_a_field_it_cannot_express(self, annotation: Any):
        """Both would build a route that silently misbehaves at runtime."""
        model = create_model("Unexpressible", field=annotation)

        with pytest.raises(TypeError):
            as_query_dependency(model)

    def test_a_field_without_a_default_stays_required(self):
        class Required(BaseModel):
            field: str

        app = FastAPI()
        router = APIRouter()

        @router.get("/things")
        def route(f: Annotated[Required, Depends(as_query_dependency(Required))]):
            return f

        app.include_router(router)
        param = app.openapi()["paths"]["/things"]["get"]["parameters"][0]

        assert param["required"] is True
        assert "default" not in param["schema"]
