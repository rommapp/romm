from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from handler import dbh

router = APIRouter()


class PlatformSchema(BaseModel):
    model_config = ConfigDict(orm_mode=True)

    igdb_id: str
    sgdb_id: str

    slug: str
    name: str

    logo_path: str
    fs_slug: str

    n_roms: int


@router.get("/platforms", status_code=200)
def platforms() -> list[PlatformSchema]:
    """Returns platforms data"""

    return dbh.get_platforms()
