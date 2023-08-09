from fastapi import APIRouter
from pydantic import BaseModel, BaseConfig

from handler import dbh

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


@router.get("/platforms", status_code=200)
def platforms() -> list[PlatformSchema]:
    """Returns platforms data"""
    return dbh.get_platforms()
