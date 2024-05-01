from pydantic import BaseModel


class FirmwareSchema(BaseModel):
    id: int

    platform_id: int
    platform_slug: str
    platform_name: str

    file_name: str
    file_name_no_tags: str
    file_name_no_ext: str
    file_extension: str
    file_path: str
    file_size_bytes: int

    full_path: str

    class Config:
        from_attributes = True
