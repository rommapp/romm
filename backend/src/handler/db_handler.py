from fastapi import HTTPException

from models.base import Session, engine, BaseModel
from models.platform import Platform
from models.rom import Rom
from logger.logger import log


class DBHandler:   
    def __init__(self) -> None:
        BaseModel.metadata.create_all(engine)
        self.session = Session()

    
    def add_platform(self, **kargs) -> None:
        self.session.merge(Platform(**kargs))

    
    def get_platforms(self) -> list[Platform]:
        return self.session.query(Platform).all()


    def add_rom(self, **kargs) -> None:
        self.session.merge(Rom(**kargs))


    def get_roms(self, p_slug: str) -> list[Rom]:
        return self.session.query(Rom).filter(Rom.p_slug == p_slug).all()
    

    def update_rom(self, p_slug: str, filename: str, data: dict) -> None:
        self.session.query(Rom).filter(Rom.p_slug==p_slug, Rom.filename==filename).update(data, synchronize_session='evaluate')


    def delete_rom(self, p_slug: str, filename: str) -> None:
        self.session.query(Rom).filter(Rom.p_slug==p_slug, Rom.filename==filename).delete(synchronize_session='evaluate')


    def commit(self):
        self.session.commit()
