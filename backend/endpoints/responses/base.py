from datetime import datetime, timezone

from pydantic import BaseModel as PydanticBaseModel
from pydantic import ConfigDict


class BaseModel(PydanticBaseModel):
    """Ensures all datetime fields include UTC timezone"""

    model_config = ConfigDict(
        json_encoders={
            datetime: lambda dt: (
                dt.isoformat()
                if dt.tzinfo
                else dt.replace(tzinfo=timezone.utc).isoformat()
            )
        }
    )
