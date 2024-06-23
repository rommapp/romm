from typing_extensions import TypedDict
from typing import NotRequired


class TokenResponse(TypedDict):
    access_token: str
    refresh_token: NotRequired[str]
    token_type: str
    expires: int
