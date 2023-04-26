from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from config import DEV_PORT, DEV_HOST
from endpoints import scan, search, platform, rom

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(scan.router)
app.include_router(search.router)
app.include_router(platform.router)
app.include_router(rom.router)


@app.on_event("startup")
def startup() -> None:
    """Startup application."""
    pass


if __name__ == '__main__':
    uvicorn.run("main:app", host=DEV_HOST, port=DEV_PORT, reload=True)
