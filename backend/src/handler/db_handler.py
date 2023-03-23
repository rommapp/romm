from fastapi import HTTPException

from sqlalchemy import select
from models.base import Session, engine, BaseModel
from models.platform import Platform
from models.rom import Rom
from logger.logger import log


class DBHandler:   
    def __init__(self) -> None:
        BaseModel.metadata.create_all(engine)
        self.session = Session()

    
    def add_platform(self, **kargs) -> None:
        with Session.begin() as session:
            session.merge(Platform(**kargs))

    
    def get_platforms(self) -> list[Platform]:
        with Session.begin() as session:
            return session.scalars(select(Platform)).all()


    def add_rom(self, **kargs) -> None:
        with Session.begin() as session:
            session.merge(Rom(**kargs))


    def get_roms(self, p_slug: str) -> list[Rom]:
        with Session.begin() as session:
            return session.scalars(select(Rom).filter_by(p_slug=p_slug)).all()
        
    
    def get_rom(self, p_slug: str, filename: str) -> Rom:
        with Session.begin() as session:
            return session.scalars(select(Rom).filter_by(p_slug=p_slug, filename=filename)).first()
    

    def update_rom(self, p_slug: str, filename: str, data: dict) -> None:
        with Session.begin() as session:
            session.query(Rom) \
                .filter(Rom.p_slug==p_slug, Rom.filename==filename) \
                .update(data, synchronize_session='evaluate')


    def delete_rom(self, p_slug: str, filename: str) -> None:
        with Session.begin() as session:
            session.query(Rom) \
                .filter(Rom.p_slug==p_slug, Rom.filename==filename) \
                .delete(synchronize_session='evaluate')
