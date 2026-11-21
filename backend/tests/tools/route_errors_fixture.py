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


def route_with_markers_in_a_swallowing_try(upstream: Response) -> Response:
    try:
        refuse()
        if upstream.headers:
            # route-errors: ignore, the test checks that this line is left out.
            return JSONResponse({}, status_code=status.HTTP_410_GONE)
        return Response(status_code=upstream.status_code)  # route-errors: raises 502
    except Exception:
        return Response()


def route_that_reraises_http_errors_first() -> None:
    try:
        refuse()
    except HTTPException:
        raise
    except Exception:
        return None


def route_with_a_status_from_its_input(code: int) -> Response:
    return Response(status_code=code)


async def route_that_offloads_a_status() -> Response:
    return await asyncio.to_thread(_respond, status.HTTP_423_LOCKED)


class Refusal(HTTPException):
    def __init__(self, code: int) -> None:
        super().__init__(status_code=code)


def route_that_raises_a_status_class() -> None:
    raise Refusal(status.HTTP_451_UNAVAILABLE_FOR_LEGAL_REASONS)


def _refuse_with(detail: str, code: int = status.HTTP_418_IM_A_TEAPOT) -> None:
    raise HTTPException(status_code=code, detail=detail)


def route_that_uses_a_default_status() -> None:
    _refuse_with("no")


def _refuse_or_fail(code: int | None = None) -> None:
    if code is None:
        code = status.HTTP_500_INTERNAL_SERVER_ERROR
    raise HTTPException(status_code=code)


def route_that_falls_back_to_a_status() -> None:
    _refuse_or_fail()


def route_with_an_unpacked_status(error: str) -> None:
    code = status.HTTP_400_BAD_REQUEST
    if error:
        code, _ = _STATUS_BY_ERROR.get(error, code), error
    raise HTTPException(status_code=code)


UPSTREAM_DOWN = status.HTTP_503_SERVICE_UNAVAILABLE


def route_with_a_status_constant() -> None:
    raise HTTPException(status_code=UPSTREAM_DOWN)


class GoneResponse(Response):
    pass


def route_that_sets_a_status(response: Response, gone: bool) -> Response:
    if gone:
        return GoneResponse(status_code=status.HTTP_410_GONE)
    response.status_code = status.HTTP_404_NOT_FOUND
    return response
