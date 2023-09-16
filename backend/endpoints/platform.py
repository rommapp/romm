from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import Optional

from handler import dbh
from utils.oauth import protected_route

router = APIRouter()


class PlatformSchema(BaseModel):
    slug: str
    fs_slug: str
    igdb_id: Optional[int] = None
    sgdb_id: Optional[int] = None
    name: Optional[str]
    logo_path: str
    rom_count: int

    class Config:
        orm_mode = True


@protected_route(router.get, "/platforms", ["platforms.read"])
def platforms(request: Request) -> list[PlatformSchema]:
    """Returns platforms data"""
    return dbh.get_platforms()
