from typing import Annotated, TypedDict

from pydantic import Field

from tasks.tasks import TaskType


class TaskInfo(TypedDict):
    name: Annotated[str, Field(description="The name of the task.")]
    type: TaskType
    manual_run: Annotated[
        bool, Field(description="Whether the task can be run manually.")
    ]
    title: Annotated[str, Field(description="The display title of the task.")]
    description: Annotated[str, Field(description="What the task does.")]
    enabled: Annotated[bool, Field(description="Whether the task is enabled.")]
    destructive: Annotated[
        bool, Field(description="Whether the task is marked destructive.")
    ]
    cron_string: Annotated[
        str,
        Field(description="The cron schedule of the task. Empty when it has none."),
    ]


class GroupedTasksDict(TypedDict):
    scheduled: list[TaskInfo]
    manual: list[TaskInfo]
    watcher: list[TaskInfo]
