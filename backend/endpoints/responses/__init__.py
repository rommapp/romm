from typing import TypedDict

from rq_scheduler.scheduler import JobStatus


class TaskExecutionResponse(TypedDict):
    task_name: str
    task_id: str
    status: JobStatus | None
    queued_at: str


class TaskStatusResponse(TaskExecutionResponse):
    started_at: str | None
    ended_at: str | None


class BulkOperationResponse(TypedDict):
    successful_items: int
    failed_items: int
    errors: list[str]
