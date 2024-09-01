from collections.abc import Callable
from typing import Any

from fastapi import APIRouter as FastAPIRouter
from fastapi.types import DecoratedCallable


class APIRouter(FastAPIRouter):
    """FastAPI router that automatically adds an alternate route with a trailing slash.

    This is needed as FastAPI does not include a built-in way to handle routes with and without
    trailing slashes, without requiring a redirect or duplicating the route definition.

    Reference: https://github.com/fastapi/fastapi/discussions/7298
    """

    def api_route(
        self, path: str, *, include_in_schema: bool = True, **kwargs: Any
    ) -> Callable[[DecoratedCallable], DecoratedCallable]:
        if path.endswith("/") and len(path) > 1:
            path = path[:-1]

        add_path = super().api_route(
            path, include_in_schema=include_in_schema, **kwargs
        )

        alternate_path = path + "/"
        add_alternate_path = super().api_route(
            alternate_path, include_in_schema=False, **kwargs
        )

        def decorator(func: DecoratedCallable) -> DecoratedCallable:
            # Path without trailing slash is registered first, for router's `url_path_for` to prefer it.
            result = add_path(func)
            add_alternate_path(func)
            return result

        return decorator
