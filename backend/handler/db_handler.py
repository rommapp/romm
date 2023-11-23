import functools

from fastapi import status, HTTPException
from sqlalchemy import create_engine, select, delete, update, and_, or_, func
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import ProgrammingError

from logger.logger import log
from config.config_loader import ConfigLoader
from models import Platform, Rom, User, Role, Save, State, Screenshot, Bios


class DBHandler:
    def __init__(self) -> None:
        self.engine = create_engine(ConfigLoader.get_db_engine(), pool_pre_ping=True)
        self.session = sessionmaker(bind=self.engine, expire_on_commit=False)

    @staticmethod
    def begin_session(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if hasattr(kwargs, "session"):
                return func(*args, session=kwargs.get("session"))

            try:
                with args[0].session.begin() as s:
                    return func(*args, session=s)
            except ProgrammingError as e:
                log.critical(str(e))
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
                )

        return wrapper

    # ========= Platforms =========
    @begin_session
    def add_platform(self, platform: Platform, session: Session = None):
        return session.merge(platform)

    @begin_session
    def get_platforms(self, session: Session = None):
        return (
            session.scalars(select(Platform).order_by(Platform.slug.asc()))
            .unique()
            .all()
        )

    @begin_session
    def get_platform(self, slug: str, session: Session = None):
        return session.get(Platform, slug)

    @begin_session
    def purge_platforms(self, platforms: list[str], session: Session = None):
        session.execute(
            delete(Save)
            .where(Save.platform_slug.not_in(platforms))
            .execution_options(synchronize_session="evaluate")
        )
        session.execute(
            delete(State)
            .where(State.platform_slug.not_in(platforms))
            .execution_options(synchronize_session="evaluate")
        )
        session.execute(
            delete(Bios)
            .where(Bios.platform_slug.not_in(platforms))
            .execution_options(synchronize_session="evaluate")
        )
        return session.execute(
            delete(Platform)
            .where(or_(Platform.slug.not_in(platforms), Platform.slug.is_(None)))
            .execution_options(synchronize_session="evaluate")
        )

    # ========= Roms =========
    @begin_session
    def add_rom(self, rom: Rom, session: Session = None):
        return session.merge(rom)

    def get_roms(self, platform_slug: str):
        return (
            select(Rom)
            .filter_by(platform_slug=platform_slug)
            .order_by(func.lower(Rom.name).asc())
        )

    @begin_session
    def get_rom(self, id, session: Session = None):
        return session.get(Rom, id)

    @begin_session
    def get_recent_roms(self, session: Session = None):
        return (
            session.scalars(select(Rom).order_by(Rom.id.desc()).limit(15))
            .all()
        )

    @begin_session
    def update_rom(self, id: int, data: dict, session: Session = None):
        return session.execute(
            update(Rom)
            .where(Rom.id == id)
            .values(**data)
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def delete_rom(self, id: int, session: Session = None):
        return session.execute(
            delete(Rom)
            .where(Rom.id == id)
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def purge_roms(self, platform_slug: str, roms: list[str], session: Session = None):
        return session.execute(
            delete(Rom)
            .where(and_(Rom.platform_slug == platform_slug, Rom.file_name.not_in(roms)))
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def get_rom_count(self, platform_slug: str, session: Session = None):
        return session.scalar(
            select(func.count()).select_from(Rom).filter_by(platform_slug=platform_slug)
        )

    # ==== Utils ======
    @begin_session
    def get_rom_by_filename(
        self, platform_slug: str, file_name: str, session: Session = None
    ):
        return session.scalars(
            select(Rom)
            .filter_by(platform_slug=platform_slug, file_name=file_name)
            .limit(1)
        ).first()

    @begin_session
    def get_rom_by_filename_no_tags(
        self, file_name_no_tags: str, session: Session = None
    ):
        return session.scalars(
            select(Rom).filter_by(file_name_no_tags=file_name_no_tags).limit(1)
        ).first()

    # ========= Saves =========
    @begin_session
    def add_save(self, save: Rom, session: Session = None):
        return session.merge(save)

    @begin_session
    def get_save(self, id, session: Session = None):
        return session.get(Save, id)
    
    @begin_session
    def update_save(self, id: int, data: dict, session: Session = None):
        session.execute(
            update(Save)
            .where(Save.id == id)
            .values(**data)
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def get_save_by_filename(
        self, platform_slug: str, file_name: str, session: Session = None
    ):
        return session.scalars(
            select(Save)
            .filter_by(platform_slug=platform_slug, file_name=file_name)
            .limit(1)
        ).first()

    @begin_session
    def purge_saves(
        self, platform_slug: str, saves: list[str], session: Session = None
    ):
        return session.execute(
            delete(Save)
            .where(
                and_(Save.platform_slug == platform_slug, Save.file_name.not_in(saves))
            )
            .execution_options(synchronize_session="evaluate")
        )

    # ========= States =========
    @begin_session
    def add_state(self, state: Rom, session: Session = None):
        return session.merge(state)

    @begin_session
    def get_state(self, id, session: Session = None):
        return session.get(State, id)
    
    @begin_session
    def update_state(self, id: int, data: dict, session: Session = None):
        session.execute(
            update(State)
            .where(State.id == id)
            .values(**data)
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def get_state_by_filename(
        self, platform_slug: str, file_name: str, session: Session = None
    ):
        return session.scalars(
            select(State)
            .filter_by(platform_slug=platform_slug, file_name=file_name)
            .limit(1)
        ).first()

    @begin_session
    def purge_states(
        self, platform_slug: str, states: list[str], session: Session = None
    ):
        return session.execute(
            delete(State)
            .where(
                and_(
                    State.platform_slug == platform_slug, State.file_name.not_in(states)
                )
            )
            .execution_options(synchronize_session="evaluate")
        )

    # ========= Bios =========
    @begin_session
    def add_bios(self, bios: Rom, session: Session = None):
        return session.merge(bios)

    @begin_session
    def get_bios(self, id, session: Session = None):
        return session.get(Bios, id)
    
    @begin_session
    def update_bios(self, id: int, data: dict, session: Session = None):
        session.execute(
            update(Bios)
            .where(Bios.id == id)
            .values(**data)
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def get_bios_by_filename(
        self, platform_slug: str, file_name: str, session: Session = None
    ):
        return session.scalars(
            select(Bios)
            .filter_by(platform_slug=platform_slug, file_name=file_name)
            .limit(1)
        ).first()

    @begin_session
    def purge_bios(self, platform_slug: str, bios: list[str], session: Session = None):
        return session.execute(
            delete(Bios)
            .where(
                and_(Bios.platform_slug == platform_slug, Bios.file_name.not_in(bios))
            )
            .execution_options(synchronize_session="evaluate")
        )

    # ========= Screenshots =========
    @begin_session
    def add_screenshot(self, screenshot: Rom, session: Session = None):
        return session.merge(screenshot)

    @begin_session
    def get_screenshot(self, id, session: Session = None):
        return session.get(Screenshot, id)
    
    @begin_session
    def update_screenshot(self, id: int, data: dict, session: Session = None):
        session.execute(
            update(Screenshot)
            .where(Screenshot.id == id)
            .values(**data)
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def get_screenshot_by_filename(self, file_name: str, session: Session = None):
        return session.scalars(
            select(Screenshot).filter_by(file_name=file_name).limit(1)
        ).first()

    @begin_session
    def purge_screenshots(self, screenshots: list[str], session: Session = None):
        return session.execute(
            delete(Screenshot)
            .where(Screenshot.file_name.not_in(screenshots))
            .execution_options(synchronize_session="evaluate")
        )

    # ========= Users =========
    @begin_session
    def add_user(self, user: User, session: Session = None):
        return session.merge(user)

    @begin_session
    def get_user_by_username(self, username: str, session: Session = None):
        return session.scalars(
            select(User).filter_by(username=username).limit(1)
        ).first()

    @begin_session
    def get_user(self, id: int, session: Session = None):
        return session.get(User, id)

    @begin_session
    def update_user(self, id: int, data: dict, session: Session = None):
        session.execute(
            update(User)
            .where(User.id == id)
            .values(**data)
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def delete_user(self, id: int, session: Session = None):
        return session.execute(
            delete(User)
            .where(User.id == id)
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def get_users(self, session: Session = None):
        return session.scalars(select(User)).all()

    @begin_session
    def get_admin_users(self, session: Session = None):
        return session.scalars(select(User).filter_by(role=Role.ADMIN)).all()
