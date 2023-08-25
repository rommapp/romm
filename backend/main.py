import uvicorn
import alembic.config
import re
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_pagination import add_pagination
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.middleware.sessions import SessionMiddleware

from config import DEV_PORT, DEV_HOST, ROMM_AUTH_SECRET_KEY, ROMM_AUTH_ENABLED
from endpoints import search, platform, rom, identity, oauth, scan  # noqa
from handler import dbh
from utils.socket import socket_app
from utils.auth import (
    HybridAuthBackend,
    CustomCSRFMiddleware,
    create_default_admin_user,
)

app = FastAPI(title="RomM API", version="0.1.0")

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

app.include_router(oauth.router)
app.include_router(identity.router)
app.include_router(platform.router)
app.include_router(rom.router)
app.include_router(search.router)

add_pagination(app)
app.mount("/ws", socket_app)


# Endpoint to set the CSRF token in cache
@app.get("/heartbeat")
def heartbeat():
    return {"ROMM_AUTH_ENABLED": ROMM_AUTH_ENABLED}


@app.on_event("startup")
def startup() -> None:
    """Startup application."""

    # Create default admin user if no admin user exists
    if len(dbh.get_admin_users()) == 0:
        create_default_admin_user()


if __name__ == "__main__":
    # Run migrations
    alembic.config.main(argv=["upgrade", "head"])

    # Run application
    uvicorn.run("main:app", host=DEV_HOST, port=DEV_PORT, reload=True)
