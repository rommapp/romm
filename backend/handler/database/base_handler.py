from config.config_manager import ConfigManager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sync_engine = create_engine(ConfigManager.get_db_engine(), pool_pre_ping=True)
sync_session = sessionmaker(bind=sync_engine, expire_on_commit=False)


class DBBaseHandler: ...
