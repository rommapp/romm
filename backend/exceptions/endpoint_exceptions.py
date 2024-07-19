from fastapi import HTTPException, status
from logger.logger import log


class PlatformNotFoundInDatabaseException(Exception):
    def __init__(self, id):
        self.message = f"Platform with id '{id}' not found"
        super().__init__(self.message)
        log.critical(self.message)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=self.message)

    def __repr__(self) -> str:
        return self.message


class RomNotFoundInDatabaseException(Exception):
    def __init__(self, id):
        self.message = f"Rom with id '{id}' not found"
        super().__init__(self.message)
        log.critical(self.message)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=self.message)

    def __repr__(self) -> str:
        return self.message


class CollectionNotFoundInDatabaseException(Exception):
    def __init__(self, id):
        self.message = f"Collection with id '{id}' not found"
        super().__init__(self.message)
        log.critical(self.message)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=self.message)

    def __repr__(self) -> str:
        return self.message


class CollectionPermissionError(Exception):
    def __init__(self, id):
        self.message = f"Permission denied for collection with id '{id}'"
        super().__init__(self.message)
        log.critical(self.message)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=self.message)

    def __repr__(self) -> str:
        return self.message


class CollectionAlreadyExistsException(Exception):
    def __init__(self, name):
        self.message = f"Collection with name '{name}' already exists"
        super().__init__(self.message)
        log.critical(self.message)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=self.message
        )

    def __repr__(self) -> str:
        return self.message
