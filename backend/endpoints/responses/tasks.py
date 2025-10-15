from typing import Dict, List, TypedDict

from tasks.tasks import TaskType


class TaskInfo(TypedDict):
    name: str
    manual_run: bool
    title: str
    description: str
    enabled: bool
    cron_string: str
    task_type: TaskType


# Use a more flexible type for grouped tasks
GroupedTasksDict = Dict[str, List[TaskInfo]]
