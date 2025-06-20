from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
# from dotenv import load_dotenv
import os
from urllib.parse import quote_plus
from .config import settings

# load_dotenv()
# PASSWORD = os.getenv("DATABASE_PASSWORD")
# encoded_password = quote_plus(PASSWORD)

SQLALCHEMY_DATABASE_URL = f'postgresql://{settings.database_username}:{quote_plus(settings.database_password)}@{settings.database_hostname}:{settings.database_port}/{settings.database_name}'

engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit = False, autoflush = False, bind = engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()