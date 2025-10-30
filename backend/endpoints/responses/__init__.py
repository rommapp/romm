from typing import Literal, TypedDict, Union

from rq_scheduler.scheduler import JobStatus

from tasks.tasks import TaskType


class ScanStats(TypedDict):
    total_platforms: int
    total_roms: int
    scanned_platforms: int
    new_platforms: int
    identified_platforms: int
    scanned_roms: int
    new_roms: int
    identified_roms: int
    scanned_firmware: int
    new_firmware: int


class ScanTaskMeta(TypedDict):
    scan_stats: ScanStats | None


class ConversionStats(TypedDict):
    processed: int
    errors: int
    total: int


class ConversionTaskMeta(TypedDict):
    conversion_stats: ConversionStats | None


class UpdateStats(TypedDict):
    processed: int
    total: int


class UpdateTaskMeta(TypedDict):
    update_stats: UpdateStats | None


class CleanupStats(TypedDict):
    platforms_in_db: int
    roms_in_db: int
    platforms_in_fs: int
    roms_in_fs: int
    removed_fs_platforms: int
    removed_fs_roms: int


class CleanupTaskMeta(TypedDict):
    cleanup_stats: CleanupStats | None


class WatcherTaskMeta(TypedDict):
    pass


class GenericTaskMeta(TypedDict):
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
    status: JobStatus
    created_at: str | None
    enqueued_at: str | None


class BaseTaskStatusResponse(TaskExecutionResponse):
    started_at: str | None
    ended_at: str | None


class ScanTaskStatusResponse(BaseTaskStatusResponse):
    task_type: Literal[TaskType.SCAN]
    meta: ScanTaskMeta


class ConversionTaskStatusResponse(BaseTaskStatusResponse):
    task_type: Literal[TaskType.CONVERSION]
    meta: ConversionTaskMeta


class UpdateTaskStatusResponse(BaseTaskStatusResponse):
    task_type: Literal[TaskType.UPDATE]
    meta: UpdateTaskMeta


class CleanupTaskStatusResponse(BaseTaskStatusResponse):
    task_type: Literal[TaskType.CLEANUP]
    meta: CleanupTaskMeta


class WatcherTaskStatusResponse(BaseTaskStatusResponse):
    task_type: Literal[TaskType.WATCHER]
    meta: WatcherTaskMeta


class GenericTaskStatusResponse(BaseTaskStatusResponse):
    task_type: Literal[TaskType.GENERIC]
    meta: GenericTaskMeta


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
