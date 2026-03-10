from typing import NotRequired, TypedDict


class TokenResponse(TypedDict):
    access_token: str
    refresh_token: NotRequired[str]
    token_type: str
    expires: int


class OIDCLogoutResponse(TypedDict):
    oidc_logout_url: str
