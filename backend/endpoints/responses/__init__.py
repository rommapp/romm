from typing import TypedDict


class TaskExecutionResponse(TypedDict):
    task_name: str
    task_id: str
    status: str
    queued_at: str


class AuthenticationResponse(TypedDict):
    user_id: int | None
    username: str | None


class ConfigurationResponse(TypedDict):
    affected_items: list[str]


class BulkOperationResponse(TypedDict):
    total_items: int
    successful_items: int
    failed_items: int
    errors: list[str] | None
