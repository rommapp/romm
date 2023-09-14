from fastapi import APIRouter, Request
from pydantic import BaseModel, BaseConfig
from typing import Optional

from handler import dbh
from utils.oauth import protected_route

router = APIRouter()


class PlatformSchema(BaseModel):
    slug: str
    fs_slug: str
    name: Optional[str]
    igdb_id: Optional[str]
    sgdb_id: Optional[str]
    logo_path: str
    rom_count: int

    class Config(BaseConfig):
        orm_mode = True


@protected_route(router.get, "/platforms", ["platforms.read"])
def platforms(request: Request) -> list[PlatformSchema]:
    """Returns platforms data"""
    return dbh.get_platforms()
