from fastapi import APIRouter

from handler import dbh

router = APIRouter()


@router.get("/platforms", status_code=200)
def platforms() -> dict:
    """Returns platforms data"""

    return {'data': dbh.get_platforms()}
