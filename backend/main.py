import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

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
    from config import DEV_PORT, DEV_HOST

    uvicorn.run("main:app", host=DEV_HOST, port=DEV_PORT, reload=True)
