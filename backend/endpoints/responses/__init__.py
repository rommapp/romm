from typing import Annotated, Literal, TypedDict, Union

from pydantic import Field
from rq.job import JobStatus

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
    updated_roms: int
    new_files: int


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


class OrphanedResourcesCleanupStats(TypedDict):
    platforms_in_db: int
    roms_in_db: int
    platforms_in_fs: int
    roms_in_fs: int
    removed_fs_platforms: int
    removed_fs_roms: int


class MissingRomsCleanupStats(TypedDict):
    platform_ids: list[int] | None
    roms_found: int
    roms_deleted: int
    errors: int


class MissingFirmwareCleanupStats(TypedDict):
    platform_ids: list[int] | None
    firmware_found: int
    firmware_deleted: int
    errors: int


CleanupStats = Union[
    OrphanedResourcesCleanupStats,
    MissingRomsCleanupStats,
    MissingFirmwareCleanupStats,
]


class CleanupTaskMeta(TypedDict):
    cleanup_stats: CleanupStats | None


class SyncTaskMeta(TypedDict):
    pass


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
    SyncTaskMeta,
    WatcherTaskMeta,
    GenericTaskMeta,
]


TASK_META_DESCRIPTION = "Details specific to this kind of task."


class TaskExecutionResponse(TypedDict):
    # None on scans started outside the catalog, by a client or the watcher.
    task_key: Annotated[
        str | None,
        Field(
            description=(
                "The key of the task in the catalog. Null for scans started"
                " outside the catalog, by a client or the watcher."
            )
        ),
    ]
    task_name: Annotated[str, Field(description="The name of the task.")]
    task_id: Annotated[
        str,
        Field(description="The job ID, which `GET /tasks/{task_id}` takes."),
    ]
    status: JobStatus
    created_at: Annotated[str | None, Field(description="When the job was created.")]
    enqueued_at: Annotated[str | None, Field(description="When the job was queued.")]


class BaseTaskStatusResponse(TaskExecutionResponse):
    started_at: Annotated[
        str | None, Field(description="When the job started running.")
    ]
    ended_at: Annotated[str | None, Field(description="When the job finished.")]


class ScanTaskStatusResponse(BaseTaskStatusResponse):
    task_type: Annotated[
        Literal[TaskType.SCAN], Field(description="The kind of task: `scan`.")
    ]
    meta: Annotated[ScanTaskMeta, Field(description=TASK_META_DESCRIPTION)]


class ConversionTaskStatusResponse(BaseTaskStatusResponse):
    task_type: Annotated[
        Literal[TaskType.CONVERSION],
        Field(description="The kind of task: `conversion`."),
    ]
    meta: Annotated[ConversionTaskMeta, Field(description=TASK_META_DESCRIPTION)]


class UpdateTaskStatusResponse(BaseTaskStatusResponse):
    task_type: Annotated[
        Literal[TaskType.UPDATE], Field(description="The kind of task: `update`.")
    ]
    meta: Annotated[UpdateTaskMeta, Field(description=TASK_META_DESCRIPTION)]


class CleanupTaskStatusResponse(BaseTaskStatusResponse):
    task_type: Annotated[
        Literal[TaskType.CLEANUP], Field(description="The kind of task: `cleanup`.")
    ]
    meta: Annotated[CleanupTaskMeta, Field(description=TASK_META_DESCRIPTION)]


class SyncTaskStatusResponse(BaseTaskStatusResponse):
    task_type: Annotated[
        Literal[TaskType.SYNC], Field(description="The kind of task: `sync`.")
    ]
    meta: Annotated[SyncTaskMeta, Field(description=TASK_META_DESCRIPTION)]


class WatcherTaskStatusResponse(BaseTaskStatusResponse):
    task_type: Annotated[
        Literal[TaskType.WATCHER], Field(description="The kind of task: `watcher`.")
    ]
    meta: Annotated[WatcherTaskMeta, Field(description=TASK_META_DESCRIPTION)]


class GenericTaskStatusResponse(BaseTaskStatusResponse):
    task_type: Annotated[
        Literal[TaskType.GENERIC], Field(description="The kind of task: `generic`.")
    ]
    meta: Annotated[GenericTaskMeta, Field(description=TASK_META_DESCRIPTION)]


TaskStatusResponse = Union[
    ScanTaskStatusResponse,
    ConversionTaskStatusResponse,
    UpdateTaskStatusResponse,
    CleanupTaskStatusResponse,
    SyncTaskStatusResponse,
    WatcherTaskStatusResponse,
    GenericTaskStatusResponse,
]


class BulkOperationResponse(TypedDict):
    successful_items: int
    failed_ids: list[int]
    errors: list[str]
