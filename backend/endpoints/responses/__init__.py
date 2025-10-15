from typing import Any, Literal, TypedDict, Union

from rq_scheduler.scheduler import JobStatus

from tasks.tasks import TaskType


class ScanStats(TypedDict):
    total_platforms: int
    total_roms: int
    scanned_platforms: int
    new_platforms: int
    identified_platforms: int
    scanned_roms: int
    added_roms: int
    metadata_roms: int
    scanned_firmware: int
    added_firmware: int


class ScanTaskMeta(TypedDict):
    scan_stats: ScanStats | None


class ConversionStats(TypedDict):
    processed: int
    errors: int
    total: int
    errorList: list[str]


class ConversionTaskMeta(TypedDict):
    conversion_stats: ConversionStats | None


class UpdateStats(TypedDict):
    progress: int
    total: int
    current: int


class UpdateTaskMeta(TypedDict):
    update_stats: UpdateStats | None


class CleanupStats(TypedDict):
    removed: int


class CleanupTaskMeta(TypedDict):
    cleanup_stats: CleanupStats | None


class WatcherTaskMeta(TypedDict):
    # Watcher tasks typically don't have complex meta
    pass


class GenericTaskMeta(TypedDict):
    # Generic tasks can have any meta structure
    pass


# Union type for all possible meta types
TaskMeta = Union[
    ScanTaskMeta,
    ConversionTaskMeta,
    UpdateTaskMeta,
    CleanupTaskMeta,
    WatcherTaskMeta,
    GenericTaskMeta,
]


class TaskExecutionResponse(TypedDict):
    task_name: str
    task_id: str
    status: JobStatus | None
    queued_at: str


class BaseTaskStatusResponse(TaskExecutionResponse):
    started_at: str | None
    ended_at: str | None
    result: dict[str, Any] | None


class ScanTaskStatusResponse(BaseTaskStatusResponse):
    task_type: Literal[TaskType.SCAN]
    meta: ScanTaskMeta | None


class ConversionTaskStatusResponse(BaseTaskStatusResponse):
    task_type: Literal[TaskType.CONVERSION]
    meta: ConversionTaskMeta | None


class UpdateTaskStatusResponse(BaseTaskStatusResponse):
    task_type: Literal[TaskType.UPDATE]
    meta: UpdateTaskMeta | None


class CleanupTaskStatusResponse(BaseTaskStatusResponse):
    task_type: Literal[TaskType.CLEANUP]
    meta: CleanupTaskMeta | None


class WatcherTaskStatusResponse(BaseTaskStatusResponse):
    task_type: Literal[TaskType.WATCHER]
    meta: WatcherTaskMeta | None


class GenericTaskStatusResponse(BaseTaskStatusResponse):
    task_type: Literal[TaskType.GENERIC]
    meta: GenericTaskMeta | None


TaskStatusResponse = Union[
    ScanTaskStatusResponse,
    ConversionTaskStatusResponse,
    UpdateTaskStatusResponse,
    CleanupTaskStatusResponse,
    WatcherTaskStatusResponse,
    GenericTaskStatusResponse,
]


class BulkOperationResponse(TypedDict):
    successful_items: int
    failed_items: int
    errors: list[str]
