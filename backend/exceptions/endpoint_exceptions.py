from fastapi import HTTPException, status

from logger.logger import log


class PlatformNotFoundInDatabaseException(Exception):
    def __init__(self, id: int) -> None:
        self.message = f"Platform with id '{id}' not found"
        super().__init__(self.message)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=self.message)

    def __repr__(self) -> str:
        return self.message


class RomNotFoundInDatabaseException(Exception):
    def __init__(self, id: int) -> None:
        self.message = f"Rom with id '{id}' not found"
        super().__init__(self.message)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=self.message)

    def __repr__(self) -> str:
        return self.message


class CollectionNotFoundInDatabaseException(Exception):
    def __init__(self, id: int | str) -> None:
        self.message = f"Collection with id '{id}' not found"
        super().__init__(self.message)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=self.message)

    def __repr__(self) -> str:
        return self.message


class CollectionPermissionError(Exception):
    def __init__(self, id: int) -> None:
        self.message = f"Permission denied for collection with id '{id}'"
        super().__init__(self.message)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=self.message)

    def __repr__(self) -> str:
        return self.message


class CollectionAlreadyExistsException(Exception):
    def __init__(self, name: str) -> None:
        self.message = f"Collection with name '{name}' already exists"
        super().__init__(self.message)
        log.critical(self.message)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=self.message)

    def __repr__(self) -> str:
        return self.message


class MusicPlaylistNotFoundException(Exception):
    def __init__(self, id: int) -> None:
        self.message = f"Playlist with id '{id}' not found"
        super().__init__(self.message)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=self.message)

    def __repr__(self) -> str:
        return self.message


class MusicPlaylistPermissionError(Exception):
    def __init__(self, id: int) -> None:
        self.message = f"Permission denied for playlist with id '{id}'"
        super().__init__(self.message)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=self.message)

    def __repr__(self) -> str:
        return self.message


class MusicPlaylistAlreadyExistsException(Exception):
    def __init__(self, name: str | None) -> None:
        self.message = f"Playlist with name '{name}' already exists"
        super().__init__(self.message)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=self.message
        )

    def __repr__(self) -> str:
        return self.message


class DeviceInstallDisabledException(Exception):
    def __init__(self) -> None:
        self.message = "Installing on a device is disabled on this server"
        super().__init__(self.message)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=self.message)

    def __repr__(self) -> str:
        return self.message


class SGDBInvalidAPIKeyException(Exception):
    def __init__(self) -> None:
        self.message = "Invalid SGDB API key"
        super().__init__(self.message)
        log.critical(self.message)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=self.message
        )

    def __repr__(self) -> str:
        return self.message
