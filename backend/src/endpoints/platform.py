from fastapi import APIRouter

from handler import dbh

router = APIRouter()


@router.get("/platforms")
def platforms() -> dict:
    """Returns platforms data"""

    return {'data': dbh.get_platforms()}
