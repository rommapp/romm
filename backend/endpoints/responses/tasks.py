from typing import Dict, List, TypedDict


class TaskInfo(TypedDict):
    name: str
    manual_run: bool
    title: str
    description: str
    enabled: bool
    cron_string: str


# Use a more flexible type for grouped tasks
GroupedTasksDict = Dict[str, List[TaskInfo]]
