from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from config.config import DB_HOST, DB_PORT, DB_USER, DB_PASSWD, DB_NAME


engine = create_engine(f"mariadb+mariadbconnector://{DB_USER}:{DB_PASSWD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
Session = sessionmaker(bind=engine)
BaseModel = declarative_base()