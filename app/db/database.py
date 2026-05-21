from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.db.models import Base


def init_db(database_url: str) -> sessionmaker:
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)
