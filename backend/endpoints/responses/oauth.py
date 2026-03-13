from typing import NotRequired, TypedDict


class TokenResponse(TypedDict):
    access_token: str
    token_type: str
    expires: int
    refresh_token: NotRequired[str]
    refresh_expires: NotRequired[int]


class OIDCLogoutResponse(TypedDict):
    oidc_logout_url: str
