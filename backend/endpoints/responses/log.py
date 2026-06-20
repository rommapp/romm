from endpoints.responses.base import BaseModel


class LogEntrySchema(BaseModel):
    """A single backend log line streamed to the admin log viewer."""

    ts: int  # epoch milliseconds
    level: str
    module: str
    message: str
