from datetime import datetime

from pydantic import BaseModel


class CollectionSchema(BaseModel):
    id: int
    name: str
    description: str
    logo_path: str = ""
    roms: set[int] = {}
    rom_count: int
    user_id: int
    user__username: str
    is_public: bool

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
