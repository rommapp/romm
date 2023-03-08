from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from logger.logger import log


def allow_cors(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    log.info("CORS enabled")
