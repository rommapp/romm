from datetime import datetime
from typing import TypedDict

from pydantic import BaseModel


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
    crc_hash: str
    md5_hash: str
    sha1_hash: str

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AddFirmwareResponse(TypedDict):
    uploaded: int
    firmware: list[FirmwareSchema]
