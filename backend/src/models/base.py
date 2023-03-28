from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from config.config import ROMM_DB_DRIVER, DB_DRIVERS

BaseModel = declarative_base()

engine = create_engine(DB_DRIVERS[ROMM_DB_DRIVER], pool_pre_ping=True)
Session = sessionmaker(bind=engine, expire_on_commit=False)
