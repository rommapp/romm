import uvicorn
import alembic.config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_pagination import add_pagination
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.middleware.sessions import SessionMiddleware

from config import DEV_PORT, DEV_HOST, SECRET_KEY
from endpoints import search, platform, rom, identity, scan  # noqa
from utils.socket import socket_app
from utils.auth import BasicAuthBackend

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    AuthenticationMiddleware,
    backend=BasicAuthBackend(),
)
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    same_site="strict",
    https_only=False, # TODO: Set to True in production
)
app.include_router(identity.router)
app.include_router(platform.router)
app.include_router(rom.router)
app.include_router(search.router)

add_pagination(app)
app.mount("/ws", socket_app)


@app.on_event("startup")
def startup() -> None:
    """Startup application."""
    pass


if __name__ == "__main__":
    # Run migrations
    alembic.config.main(argv=["upgrade", "head"])

    # Run application
    uvicorn.run("main:app", host=DEV_HOST, port=DEV_PORT, reload=True)
