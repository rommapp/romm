import re
import sys

import alembic.config
import uvicorn
from config import DEV_HOST, DEV_PORT, ROMM_AUTH_ENABLED, ROMM_AUTH_SECRET_KEY
from endpoints import (
    auth,
    config,
    heartbeat,
    platform,
    rom,
    raw,
    saves,
    search,
    states,
    stats,
    tasks,
    user,
    webrcade,
)
import endpoints.sockets.scan # noqa
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_pagination import add_pagination
from handler import auth_handler, db_user_handler, github_handler, socket_handler
from handler.auth_handler.hybrid_auth import HybridAuthBackend
from handler.auth_handler.middleware import CustomCSRFMiddleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.middleware.sessions import SessionMiddleware

app = FastAPI(title="RomM API", version=github_handler.get_version())

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if ROMM_AUTH_ENABLED and "pytest" not in sys.modules:
    # CSRF protection (except endpoints listed in exempt_urls)
    app.add_middleware(
        CustomCSRFMiddleware,
        secret=ROMM_AUTH_SECRET_KEY,
        exempt_urls=[re.compile(r"^/token.*"), re.compile(r"^/ws")],
    )

# Handles both basic and oauth authentication
app.add_middleware(
    AuthenticationMiddleware,
    backend=HybridAuthBackend(),
)

# Enables support for sessions on requests
app.add_middleware(
    SessionMiddleware,
    secret_key=ROMM_AUTH_SECRET_KEY,
    same_site="strict",
    https_only=False,
)

app.include_router(heartbeat.router)
app.include_router(auth.router)
app.include_router(user.router)
app.include_router(platform.router)
app.include_router(rom.router)
app.include_router(search.router)
app.include_router(saves.router)
app.include_router(states.router)
app.include_router(tasks.router)
app.include_router(webrcade.router)
app.include_router(config.router)
app.include_router(stats.router)
app.include_router(raw.router)

add_pagination(app)
app.mount("/ws", socket_handler.socket_app)


@app.on_event("startup")
def startup() -> None:
    """Event to handle RomM startup logic."""

    # Create default admin user if no admin user exists
    if len(db_user_handler.get_admin_users()) == 0 and "pytest" not in sys.modules:
        auth_handler.create_default_admin_user()


if __name__ == "__main__":
    # Run migrations
    alembic.config.main(argv=["upgrade", "head"])

    # Run application
    uvicorn.run("main:app", host=DEV_HOST, port=DEV_PORT, reload=True)
