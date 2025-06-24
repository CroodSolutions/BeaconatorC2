from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from typing import Tuple as PyTuple
from .models import Base
from .repository import AgentRepository

def setup_database(db_path: str) -> PyTuple[sessionmaker, AgentRepository]:
    """Setup database and return session factory and repository"""
    engine = create_engine(f'sqlite:///{db_path}')
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal, AgentRepository(SessionLocal)