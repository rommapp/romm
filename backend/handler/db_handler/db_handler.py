from config.config_manager import ConfigManager
from decorators.database import begin_session
from models import Role, Rom, Save, Screenshot, State, User
from sqlalchemy import and_, create_engine, delete, func, select, update
from sqlalchemy.orm import Session, sessionmaker


class DBHandler:
    def __init__(self) -> None:
        self.engine = create_engine(ConfigManager.get_db_engine(), pool_pre_ping=True)
        self.session = sessionmaker(bind=self.engine, expire_on_commit=False)

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
    def get_rom(self, id: int, session: Session = None):
        return session.get(Rom, id)

    @begin_session
    def get_recent_roms(self, session: Session = None):
        return session.scalars(select(Rom).order_by(Rom.id.desc()).limit(15)).all()

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
    def purge_roms(self, platform_id: int, roms: list[str], session: Session = None):
        return session.execute(
            delete(Rom)
            .where(and_(Rom.platform_id == platform_id, Rom.file_name.not_in(roms)))
            .execution_options(synchronize_session="evaluate")
        )

    # ==== Utils ======
    @begin_session
    def get_rom_by_filename(
        self, platform_id: int, file_name: str, session: Session = None
    ):
        return session.scalars(
            select(Rom).filter_by(platform_id=platform_id, file_name=file_name).limit(1)
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
    def add_save(self, save: Save, session: Session = None):
        return session.merge(save)

    @begin_session
    def get_save(self, id, session: Session = None):
        return session.get(Save, id)

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
    def update_save(self, id: int, data: dict, session: Session = None):
        session.execute(
            update(Save)
            .where(Save.id == id)
            .values(**data)
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def delete_save(self, id: int, session: Session = None):
        return session.execute(
            delete(Save)
            .where(Save.id == id)
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def purge_saves(self, platform_id: int, saves: list[str], session: Session = None):
        return session.execute(
            delete(Save)
            .where(and_(Save.platform_id == platform_id, Save.file_name.not_in(saves)))
            .execution_options(synchronize_session="evaluate")
        )

    # ========= States =========
    @begin_session
    def add_state(self, state: State, session: Session = None):
        return session.merge(state)

    @begin_session
    def get_state(self, id, session: Session = None):
        return session.get(State, id)

    @begin_session
    def get_state_by_filename(
        self, platform_id: int, file_name: str, session: Session = None
    ):
        return session.scalars(
            select(State)
            .filter_by(platform_slug=platform_id, file_name=file_name)
            .limit(1)
        ).first()

    @begin_session
    def update_state(self, id: int, data: dict, session: Session = None):
        session.execute(
            update(State)
            .where(State.id == id)
            .values(**data)
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def delete_state(self, id: int, session: Session = None):
        return session.execute(
            delete(State)
            .where(State.id == id)
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def purge_states(
        self, platform_id: int, states: list[str], session: Session = None
    ):
        return session.execute(
            delete(State)
            .where(
                and_(State.platform_id == platform_id, State.file_name.not_in(states))
            )
            .execution_options(synchronize_session="evaluate")
        )

    # ========= Screenshots =========
    @begin_session
    def add_screenshot(self, screenshot: Screenshot, session: Session = None):
        return session.merge(screenshot)

    @begin_session
    def get_screenshot(self, id, session: Session = None):
        return session.get(Screenshot, id)

    @begin_session
    def get_screenshot_by_filename(self, file_name: str, session: Session = None):
        return session.scalars(
            select(Screenshot).filter_by(file_name=file_name).limit(1)
        ).first()

    @begin_session
    def update_screenshot(self, id: int, data: dict, session: Session = None):
        session.execute(
            update(Screenshot)
            .where(Screenshot.id == id)
            .values(**data)
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def delete_screenshot(self, id: int, session: Session = None):
        return session.execute(
            delete(Screenshot)
            .where(Screenshot.id == id)
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def purge_screenshots(
        self, platform_id: int, screenshots: list[str], session: Session = None
    ):
        return session.execute(
            delete(Screenshot)
            .where(
                Screenshot.platform_id == platform_id,
                Screenshot.file_name.not_in(screenshots),
            )
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
