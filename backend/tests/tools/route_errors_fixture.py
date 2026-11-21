"""Routes for test_route_errors."""

import asyncio
from typing import Annotated

from fastapi import Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse


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


def route_that_returns_an_error(found: bool) -> JSONResponse:
    if found:
        return JSONResponse({})
    return JSONResponse({}, status_code=status.HTTP_410_GONE)


def _respond(status_code: int) -> Response:
    return Response(status_code=status_code)


def route_that_forwards_a_status(locked: bool) -> Response:
    return _respond(status.HTTP_423_LOCKED if locked else status.HTTP_204_NO_CONTENT)


_STATUS_BY_ERROR = {"bad": status.HTTP_400_BAD_REQUEST}


def route_with_a_status_map(error: str) -> None:
    raise HTTPException(
        status_code=_STATUS_BY_ERROR.get(error, status.HTTP_502_BAD_GATEWAY)
    )


def route_with_a_status_variable() -> None:
    code = status.HTTP_403_FORBIDDEN
    raise HTTPException(status_code=code)


def route_with_an_unreadable_status(upstream: Response) -> Response:
    return Response(status_code=upstream.status_code)


def route_that_refuses_input() -> None:
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT)


def route_with_input_that_it_refuses(name: str) -> None:
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT)


def refuse_in_a_thread() -> None:
    raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT)


async def route_that_offloads() -> None:
    await asyncio.to_thread(refuse_in_a_thread)


def route_that_swallows_errors() -> Response:
    try:
        refuse()
        return JSONResponse({}, status_code=status.HTTP_410_GONE)
    except Exception:
        return Response()


def route_that_reraises() -> None:
    try:
        refuse()
    except Exception:
        raise


def route_with_a_declared_status(upstream: Response) -> Response:
    return Response(status_code=upstream.status_code)  # route-errors: raises 502


def route_with_a_declared_status_above(upstream: Response) -> Response:
    # route-errors: raises 502, 503
    return Response(status_code=upstream.status_code)
