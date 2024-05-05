from pydantic import BaseModel
from typing_extensions import TypedDict


class FirmwareSchema(BaseModel):
    id: int

    file_name: str
    file_name_no_tags: str
    file_name_no_ext: str
    file_extension: str
    file_path: str
    file_size_bytes: int

    full_path: str
    is_verified: bool

    class Config:
        from_attributes = True


class AddFirmwareResponse(TypedDict):
    uploaded: int
    firmware: list[FirmwareSchema]
