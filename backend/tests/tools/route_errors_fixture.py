"""Routes whose only error comes from a dependency, for test_route_errors."""

from typing import Annotated

from fastapi import Depends, HTTPException, status


def refuse() -> None:
    raise HTTPException(status_code=status.HTTP_409_CONFLICT)


RefusedParam = Annotated[None, Depends(refuse)]


def route_with_a_default(param: None = Depends(refuse)) -> None: ...


def route_with_an_alias(param: RefusedParam) -> None: ...
