from fastapi import APIRouter

from handler import dbh

router = APIRouter()


@router.get("/platforms", status_code=200)
def platforms():
    """Returns platforms data"""

    return dbh.get_platforms()
