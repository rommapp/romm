from config.config_manager import ConfigManager
from decorators.database import begin_session
from models import Role, Rom, Save, Screenshot, State, User
from sqlalchemy import and_, create_engine, delete, func, select, update
from sqlalchemy.orm import Session, sessionmaker


class DBHandler:
    def __init__(self) -> None:
        self.engine = create_engine(ConfigManager.get_db_engine(), pool_pre_ping=True)
        self.session = sessionmaker(bind=self.engine, expire_on_commit=False)

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
        self, rom_id: int, screenshots: list[str], session: Session = None
    ):
        return session.execute(
            delete(Screenshot)
            .where(
                Screenshot.rom_id == rom_id,
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
    
    # ========= Stats =========
    @begin_session
    def get_platforms_count(self, session: Session = None):
        # Only count platforms with more then 0 roms
        return session.scalar(
            select(func.count())
            .select_from(Platform)
            .where(
                select(func.count())
                .select_from(Rom)
                .filter_by(platform_slug=Platform.slug)
                .as_scalar()
                > 0
            )
        )

    @begin_session
    def get_roms_count(self, session: Session = None) -> int:
        return session.scalar(select(func.count()).select_from(Rom))

    @begin_session
    def get_saves_count(self, session: Session = None) -> int:
        return session.scalar(select(func.count()).select_from(Save))

    @begin_session
    def get_states_count(self, session: Session = None) -> int:
        return session.scalar(select(func.count()).select_from(State))

    @begin_session
    def get_screenshots_count(self, session: Session = None) -> int:
        return session.scalar(select(func.count()).select_from(Screenshot))

    @begin_session
    def get_total_filesize(self, session: Session = None) -> int:
        return 0
