from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
# from dotenv import load_dotenv
import os
from urllib.parse import quote_plus
from .config import settings
from contextlib import contextmanager

# load_dotenv()
# PASSWORD = os.getenv("DATABASE_PASSWORD")
# encoded_password = quote_plus(PASSWORD)

SQLALCHEMY_DATABASE_URL = f'postgresql://{settings.supabase_database_username}:{quote_plus(settings.supabase_database_password)}@{settings.supabase_database_hostname}:{settings.supabase_database_port}/{settings.supabase_database_name}'

# print(SQLALCHEMY_DATABASE_URL)

# postgresql://postgres:[YOUR-PASSWORD]@db.lavarwuonkcywpzbthsc.supabase.co:5432/postgres

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"sslmode": "require"},
    pool_pre_ping=True
    )

SessionLocal = sessionmaker(autocommit = False, autoflush = False, bind = engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        
from contextlib import contextmanager

@contextmanager
def session_scope():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except:
        db.rollback()
        raise
    finally:
        db.close()
