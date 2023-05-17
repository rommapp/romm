import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import DEV_PORT, DEV_HOST
from handler.socket_manager import SocketManager
from endpoints import scan, search, platform, rom

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(search.router)
app.include_router(platform.router)
app.include_router(rom.router)

sm = SocketManager()
sm.mount_to("/ws", app)


async def scan_handler(*args):
    await scan.scan(*args, sm)


async def mass_rename_handler(*args):
    await rom.rename_all_roms(*args, sm)


sm.on("scan", handler=scan_handler)
sm.on("mass_rename", handler=mass_rename_handler)


@app.on_event("startup")
def startup() -> None:
    """Startup application."""
    pass


if __name__ == "__main__":
    uvicorn.run("main:app", host=DEV_HOST, port=DEV_PORT, reload=True)
    # uvicorn.run("main:app", host=DEV_HOST, port=DEV_PORT, reload=False, workers=2)
