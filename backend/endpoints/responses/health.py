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


class HealthLiveResponse(TypedDict):
    status: Literal["ok"]


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


class DatabaseStatus(TypedDict):
    ok: bool
    latency_ms: int
    error: CheckError | None


class ValkeyStatus(TypedDict):
    ok: bool
    latency_ms: int
    error: CheckError | None


class WorkerStatus(TypedDict):
    ok: bool
    latency_ms: int
    error: CheckError | None
    workers: int
    queues: dict[str, int]


class MigrationStatus(TypedDict):
    ok: bool
    latency_ms: int
    error: CheckError | None
    current: str | None
    head: str | None


class HealthStatusResponse(TypedDict):
    database: DatabaseStatus
    valkey: ValkeyStatus
    worker: WorkerStatus
    migration: MigrationStatus
    library: LibraryCheck
    resources: ResourcesCheck
