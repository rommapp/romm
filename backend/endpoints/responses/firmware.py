from typing import TypedDict

from pydantic import ConfigDict

from .base import BaseModel, UTCDatetime


class FirmwareSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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

    missing_from_fs: bool

    created_at: UTCDatetime
    updated_at: UTCDatetime


class AddFirmwareResponse(TypedDict):
    uploaded: int
    firmware: list[FirmwareSchema]
