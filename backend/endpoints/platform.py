from fastapi import APIRouter, Request
from pydantic import BaseModel, BaseConfig

from handler import dbh
from utils.oauth import protected_route

router = APIRouter()


class PlatformSchema(BaseModel):
    igdb_id: str
    sgdb_id: str

    slug: str
    name: str

    logo_path: str
    fs_slug: str

    n_roms: int

    class Config(BaseConfig):
        orm_mode = True


@protected_route(router.get, "/platforms", ["platforms.read"])
def platforms(request: Request) -> list[PlatformSchema]:
    """Returns platforms data"""
    return dbh.get_platforms()
