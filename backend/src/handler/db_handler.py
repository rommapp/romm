from fastapi import HTTPException

from models.base import Session, engine, BaseModel
from models.platform import Platform
from models.rom import Rom
from logger.logger import log


class DBHandler:   
    def __init__(self) -> None:
        BaseModel.metadata.create_all(engine)
        self.session = Session()

    
    def add_platform(self, **kargs):
        self.session.merge(Platform(**kargs))

    
    def get_platforms(self):
        return self.session.query(Platform).all()


    def add_rom(self, **kargs):
        self.session.merge(Rom(**kargs))


    def get_roms(self, p_slug):
        return self.session.query(Rom).filter(Rom.p_slug == p_slug).all()


    def commit(self):
        self.session.commit()
