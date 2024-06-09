from typing import Optional

from fastapi import UploadFile
from fastapi.param_functions import Form


class UserForm:
    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        role: Optional[str] = None,
        enabled: Optional[bool] = None,
        avatar: Optional[UploadFile] = None,
    ):
        self.username = username
        self.password = password
        self.role = role
        self.enabled = enabled
        self.avatar = avatar


class OAuth2RequestForm:
    def __init__(
        self,
        grant_type: str = Form(default="password"),
        scope: str = Form(default=""),
        username: Optional[str] = Form(default=None),
        password: Optional[str] = Form(default=None),
        client_id: Optional[str] = Form(default=None),
        client_secret: Optional[str] = Form(default=None),
        refresh_token: Optional[str] = Form(default=None),
    ):
        self.grant_type = grant_type
        self.scopes = scope.split()
        self.username = username
        self.password = password
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
