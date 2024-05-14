from config.config_manager import ConfigManager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class DBBaseHandler:
    def __init__(self) -> None:
        self.engine = create_engine(ConfigManager.get_db_engine(), pool_pre_ping=True)
        self.session = sessionmaker(bind=self.engine, expire_on_commit=False)
