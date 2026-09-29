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


class InstallSessionNotFoundException(Exception):
    def __init__(self, rom_id):
        self.message = f"No install session found for rom with id '{rom_id}'"
        super().__init__(self.message)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=self.message)

    def __repr__(self) -> str:
        return self.message


class InstallSessionRunningException(Exception):
    def __init__(self, rom_id):
        self.message = (
            f"Install for rom '{rom_id}' is still running; "
            "wait for it to finish (or fail) before clearing its cache"
        )
        super().__init__(self.message)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=self.message)

    def __repr__(self) -> str:
        return self.message


class InstallSessionHasViewersException(Exception):
    def __init__(self, rom_id, viewer_count: int):
        self.message = (
            f"Install cache for rom '{rom_id}' is currently being downloaded "
            f"by {viewer_count} client(s); wait for them to finish before "
            "clearing it"
        )
        super().__init__(self.message)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=self.message)

    def __repr__(self) -> str:
        return self.message


class InstallSessionNotActiveException(Exception):
    def __init__(self, rom_id):
        self.message = f"No running install for rom '{rom_id}' to cancel"
        super().__init__(self.message)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=self.message)

    def __repr__(self) -> str:
        return self.message


class InstallWorkerUnavailableException(Exception):
    def __init__(self):
        self.message = (
            "No install worker is currently connected; the install-sandbox "
            "worker may not be running. Try again once it's up."
        )
        super().__init__(self.message)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=self.message
        )

    def __repr__(self) -> str:
        return self.message


class InstallConcurrencyLimitException(Exception):
    def __init__(self, max_concurrency: int):
        self.message = (
            f"Maximum of {max_concurrency} concurrent install(s) already running; "
            "try again once one finishes"
        )
        super().__init__(self.message)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=self.message
        )

    def __repr__(self) -> str:
        return self.message


class ProtonBuildNotFoundException(Exception):
    def __init__(self, build_id: str):
        self.message = (
            f"Proton build '{build_id}' not found or not available for download"
        )
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=self.message
        )

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


class RomNotFoundInRetroAchievementsException(Exception):
    def __init__(self, id: int) -> None:
        self.message = f"Rom with id '{id}' does not exist on RetroAchievements"
        super().__init__(self.message)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=self.message)


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
