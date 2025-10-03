from __future__ import annotations

import functools
from typing import Any, Callable

import socketio  # type: ignore
from starlette.requests import HTTPConnection

from exceptions.auth_exceptions import AuthenticationRequiredError, AuthorizationError
from handler.auth.constants import READ_SCOPES, WRITE_SCOPES
from handler.auth.hybrid_auth import HybridAuthBackend
from logger.logger import log


def get_socket_connection(
    sid: str, socket_manager: socketio.AsyncRedisManager
) -> HTTPConnection | None:
    """Extract HTTPConnection from socket session for authentication."""
    try:
        # Get the socket session data
        session_data = socket_manager.get_session(sid)
        if not session_data:
            return None

        # Use the session data that was already parsed during connection
        session = session_data.get("session", {})

        # Create a mock HTTPConnection with the session data
        scope = {
            "type": "websocket",
            "session": session,
            "headers": session_data.get("headers", []),
        }

        return HTTPConnection(scope)
    except Exception as e:
        log.debug(f"Failed to get socket connection for sid {sid}: {e}")
        return None


async def authenticate_socket_user(
    sid: str, socket_manager: socketio.AsyncRedisManager
) -> tuple[Any, list[str]]:
    """Authenticate user from socket session and return user and scopes."""
    connection = get_socket_connection(sid, socket_manager)
    if not connection:
        raise AuthenticationRequiredError("No valid session found")

    # Use the hybrid auth backend to authenticate
    auth_backend = HybridAuthBackend()
    auth_result = await auth_backend.authenticate(connection)

    if not auth_result:
        raise AuthenticationRequiredError("Authentication failed")

    credentials, user = auth_result
    return user, credentials.scopes


def require_socket_auth(scopes: list[str] | None = None):
    """Decorator to require authentication for socket handlers."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(sid: str, *args, **kwargs):
            try:
                # Import socket_handler here to avoid circular imports
                from handler.socket_handler import socket_handler

                # Get socket manager from the socket handler
                socket_manager = socket_handler.socket_server.manager

                # Authenticate user
                user, user_scopes = await authenticate_socket_user(sid, socket_manager)

                # Check scopes if required
                if scopes:
                    required_scopes = set(scopes)
                    user_scope_set = set(user_scopes)
                    if not required_scopes.intersection(user_scope_set):
                        raise AuthorizationError(
                            f"Required scopes {scopes} not found in user scopes {user_scopes}"
                        )

                # Add user to kwargs for use in handler
                kwargs["_authenticated_user"] = user
                kwargs["_user_scopes"] = user_scopes

                return await func(sid, *args, **kwargs)

            except (AuthenticationRequiredError, AuthorizationError) as e:
                log.warning(f"Socket authentication failed for sid {sid}: {e}")
                from handler.socket_handler import socket_handler

                await socket_handler.socket_server.emit(
                    "error", {"message": str(e)}, room=sid
                )
                return None
            except Exception as e:
                log.error(
                    f"Unexpected error in socket authentication for sid {sid}: {e}"
                )
                from handler.socket_handler import socket_handler

                await socket_handler.socket_server.emit(
                    "error", {"message": "Internal server error"}, room=sid
                )
                return None

        return wrapper

    return decorator


def require_socket_write_auth(func: Callable) -> Callable:
    """Convenience decorator for write operations requiring write scopes."""
    return require_socket_auth(list(WRITE_SCOPES))(func)


def require_socket_read_auth(func: Callable) -> Callable:
    """Convenience decorator for read operations requiring read scopes."""
    return require_socket_auth(list(READ_SCOPES))(func)
