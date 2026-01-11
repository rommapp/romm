from typing import TypedDict


class SFUTokenResponse(TypedDict):
    token: str
    token_type: str
    expires: int
