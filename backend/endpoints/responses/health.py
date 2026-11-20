from typing import Literal, TypedDict

# Stable codes, so monitors can alert without parsing text.
CheckError = Literal[
    "timeout",
    "unreachable",
    "error",
    "no_workers",
    "behind",
    "ahead",
    "unreadable",
    "unwritable",
]


class ReadyCheck(TypedDict):
    ok: bool
    error: CheckError | None


class LibraryCheck(TypedDict):
    ok: bool
    readable: bool
    error: CheckError | None


class ResourcesCheck(TypedDict):
    ok: bool
    readable: bool
    writable: bool
    error: CheckError | None


class HealthReadyResponse(TypedDict):
    database: ReadyCheck
    valkey: ReadyCheck
    worker: ReadyCheck
    migration: ReadyCheck
    library: LibraryCheck
    resources: ResourcesCheck
