from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from config.config_loader import get_db_engine

BaseModel = declarative_base()

engine = create_engine(get_db_engine(), pool_pre_ping=True)
Session = sessionmaker(bind=engine, expire_on_commit=False)
