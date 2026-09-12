import inspect
from collections.abc import Callable
from typing import Annotated, Any

from fastapi import APIRouter as FastAPIRouter
from fastapi import Query
from fastapi.types import DecoratedCallable
from pydantic import BaseModel


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


def as_query_dependency[ModelT: BaseModel](
    model: type[ModelT],
) -> Callable[..., ModelT]:
    """Expose a model's fields as the individual query parameters of a route.

    `Annotated[Model, Query()]` does this natively, but only on a route whose
    *only* query parameter is the model (FastAPI's
    `_get_flat_fields_from_params`). With any other one present the model stays
    a single parameter named after the argument, which both documents the route
    wrongly and makes it reject the fields it should accept. A dependency's
    parameters are flattened individually, so this builds one whose signature
    carries the fields, each with its own constraints.
    """

    parameters = [
        inspect.Parameter(
            name,
            inspect.Parameter.KEYWORD_ONLY,
            default=field.get_default(call_default_factory=True),
            annotation=Annotated[
                field.annotation,
                *field.metadata,
                Query(description=field.description),
            ],
        )
        for name, field in model.model_fields.items()
    ]

    def dependency(**kwargs: Any) -> ModelT:
        return model(**kwargs)

    dependency.__signature__ = inspect.Signature(parameters)  # type: ignore[attr-defined]
    return dependency
