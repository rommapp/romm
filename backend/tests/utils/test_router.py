import itertools

import pytest
from fastapi import Request

from utils.router import APIRouter


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
