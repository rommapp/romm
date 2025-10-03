from fastapi import HTTPException, status


class AuthenticationRequiredError(Exception):
    """Raised when authentication is required but not provided."""

    pass


class AuthorizationError(Exception):
    """Raised when user lacks required permissions."""

    pass


AuthCredentialsException = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Incorrect username or password",
)

AuthenticationSchemeException = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid authentication scheme",
)

UserDisabledException = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Disabled user",
)

OAuthCredentialsException = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)

OIDCDisabledException = HTTPException(
    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    detail="OAuth disabled",
)

OIDCNotConfiguredException = HTTPException(
    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    detail="OAuth not configured",
)
