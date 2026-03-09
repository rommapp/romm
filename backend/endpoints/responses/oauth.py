from typing import NotRequired, TypedDict


class TokenResponse(TypedDict):
    access_token: str
    refresh_token: NotRequired[str]
    token_type: str
    expires_in: int
    refresh_expires_in: int
