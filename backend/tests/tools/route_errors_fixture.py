"""Routes for test_route_errors, each raising at most a 409 from `refuse`."""

import asyncio
from typing import Annotated

from fastapi import Depends, HTTPException, status


def refuse() -> None:
    raise HTTPException(status_code=status.HTTP_409_CONFLICT)


RefusedParam = Annotated[None, Depends(refuse)]


def route_with_a_default(param: None = Depends(refuse)) -> None: ...


def route_with_an_alias(param: RefusedParam) -> None: ...


async def refuse_later() -> None:
    refuse()


async def route_that_gathers_errors() -> None:
    await asyncio.gather(refuse_later(), return_exceptions=True)


async def route_that_gathers() -> None:
    await asyncio.gather(refuse_later())


def route_with_an_ignored_call() -> None:
    # route-errors: ignore, the test checks that this call is left out.
    refuse()


def route_with_an_ignored_trailing_call() -> None:
    refuse()  # route-errors: ignore, the test checks that this call is left out.
