from fastapi import HTTPException, status


credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Incorrect username or password",
)

authentication_scheme_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid authentication scheme",
)

disabled_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Disabled user",
)
