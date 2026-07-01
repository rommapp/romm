import asyncio
import logging.config
import re
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress

import alembic.config
import sentry_sdk
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_pagination import add_pagination
from starlette.middleware.authentication import AuthenticationMiddleware
from startup import main

import endpoints.sockets.activity  # noqa
import endpoints.sockets.logs  # noqa
import endpoints.sockets.netplay  # noqa
import endpoints.sockets.scan  # noqa
import endpoints.sockets.sync  # noqa
from config import (
    DEV_HOST,
    DEV_PORT,
    DISABLE_CSRF_PROTECTION,
    IS_PYTEST_RUN,
    OIDC_ENABLED,
    ROMM_AUTH_SECRET_KEY,
    SENTRY_DSN,
)
from endpoints.activity import router as activity_router
from endpoints.auth import router as auth_router
from endpoints.client_tokens import router as client_tokens_router
from endpoints.collections import router as collections_router
from endpoints.configs import router as configs_router
from endpoints.device import router as device_router
from endpoints.device_auth import router as device_auth_router
from endpoints.export import router as export_router
from endpoints.feeds import router as feeds_router
from endpoints.firmware import router as firmware_router
from endpoints.heartbeat import router as heartbeat_router
from endpoints.logs import router as logs_router
from endpoints.netplay import router as netplay_router
from endpoints.permissions import router as permissions_router
from endpoints.platform import router as platform_router
from endpoints.play_sessions import router as play_sessions_router
from endpoints.roms import router as rom_router
from endpoints.saves import router as saves_router
from endpoints.screenshots import router as screenshots_router
from endpoints.search import router as search_router
from endpoints.states import router as states_router
from endpoints.stats import router as stats_router
from endpoints.sync import router as sync_router
from endpoints.tasks import router as tasks_router
from endpoints.user import router as user_router
from handler.auth.constants import SESSION_COOKIE_NAME
from handler.auth.hybrid_auth import HybridAuthBackend
from handler.auth.middleware.csrf_middleware import CSRFMiddleware
from handler.auth.middleware.redis_session_middleware import RedisSessionMiddleware
from handler.socket_handler import netplay_socket_handler, socket_handler
from logger.formatter import LOGGING_CONFIG
from utils import get_version
from utils.context import (
    ctx_aiohttp_session,
    ctx_httpx_client,
    initialize_context,
    set_context_middleware,
)

logging.config.dictConfig(LOGGING_CONFIG)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    async with initialize_context():
        app.state.aiohttp_session = ctx_aiohttp_session.get()
        app.state.httpx_client = ctx_httpx_client.get()

        # Relay backend log lines to admin Socket.IO clients in real time.
        log_forwarder_task: asyncio.Task[None] | None = None
        if not IS_PYTEST_RUN:
            from endpoints.sockets.logs import start_log_forwarder

            log_forwarder_task = asyncio.create_task(start_log_forwarder())

        try:
            yield
        finally:
            if log_forwarder_task is not None:
                log_forwarder_task.cancel()
                # Await the cancellation so the forwarder's cleanup (pubsub
                # close, lock release) finishes before shutdown completes.
                with suppress(asyncio.CancelledError):
                    await log_forwarder_task


sentry_sdk.init(
    dsn=SENTRY_DSN,
    release="romm@" + get_version(),
)

app = FastAPI(
    title="RomM API",
    version=get_version(),
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if not IS_PYTEST_RUN and not DISABLE_CSRF_PROTECTION:
    # CSRF protection (except endpoints listed in exempt_urls)
    app.add_middleware(
        CSRFMiddleware,
        cookie_name="romm_csrftoken",
        secret=ROMM_AUTH_SECRET_KEY,
        exempt_urls=[
            re.compile(r"^/api/token.*"),
            re.compile(r"^/api/client-tokens/exchange"),
            re.compile(r"^/api/client-tokens/pair/.+/status"),
            re.compile(r"^/api/auth/device/init/?$"),
            re.compile(r"^/api/auth/device/token/?$"),
            re.compile(r"^/ws"),
            re.compile(r"^/netplay"),
        ],
    )

# Handles both basic and oauth authentication
app.add_middleware(
    AuthenticationMiddleware,
    backend=HybridAuthBackend(),
)

# Enables support for sessions on requests
app.add_middleware(
    RedisSessionMiddleware,
    session_cookie=SESSION_COOKIE_NAME,
    same_site="lax" if OIDC_ENABLED else "strict",
    https_only=False,
)

# Sets context vars in request-response cycle
app.middleware("http")(set_context_middleware)

app.include_router(heartbeat_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(activity_router, prefix="/api")
app.include_router(user_router, prefix="/api")
app.include_router(client_tokens_router, prefix="/api")
app.include_router(device_router, prefix="/api")
app.include_router(device_auth_router, prefix="/api")
app.include_router(play_sessions_router, prefix="/api")
app.include_router(platform_router, prefix="/api")
app.include_router(rom_router, prefix="/api")
app.include_router(search_router, prefix="/api")
app.include_router(saves_router, prefix="/api")
app.include_router(states_router, prefix="/api")
app.include_router(sync_router, prefix="/api")
app.include_router(tasks_router, prefix="/api")
app.include_router(feeds_router, prefix="/api")
app.include_router(configs_router, prefix="/api")
app.include_router(stats_router, prefix="/api")
app.include_router(logs_router, prefix="/api")
app.include_router(screenshots_router, prefix="/api")
app.include_router(firmware_router, prefix="/api")
app.include_router(collections_router, prefix="/api")
app.include_router(export_router, prefix="/api")
app.include_router(netplay_router, prefix="/api")
app.include_router(permissions_router, prefix="/api")

app.mount("/ws", socket_handler.socket_app)
app.mount("/netplay", netplay_socket_handler.socket_app)

add_pagination(app)


# NOTE: This code is only executed when running the application directly,
# not by deployments using gunicorn.
if __name__ == "__main__":
    # Run migrations
    alembic.config.main(argv=["upgrade", "head"])

    # Run startup tasks
    asyncio.run(main())

    # Run application
    uvicorn.run("main:app", host=DEV_HOST, port=DEV_PORT, reload=True, access_log=False)
