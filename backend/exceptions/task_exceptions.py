class TaskNotFoundException(Exception):
    def __init__(self, name: str) -> None:
        self.message = f"No task is registered under the name '{name}'"
        super().__init__(self.message)

    def __repr__(self) -> str:
        return self.message
