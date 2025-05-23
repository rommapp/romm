import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from user_agents import parse as parse_user_agent

log = logging.getLogger("uvicorn.access")


class CustomLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time

        client_addr = request.client.host if request.client else "-"
        method = request.method
        path = request.url.path
        status_code = response.status_code
        length = response.headers.get("content-length", "-")
        ua_string = request.headers.get("user-agent", "-")
        ua = parse_user_agent(ua_string)

        browser = ua.browser.family
        os = ua.os.family

        log_msg = (
            f"{client_addr} | "
            f"{method} {path} {status_code} | {length} | "
            f"{browser} {os} | {process_time:.3f}"
        )

        log.info(log_msg)
        return response
