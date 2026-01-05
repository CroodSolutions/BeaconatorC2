from typing import Tuple as PyTuple
import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .models import Base
from .repository import BeaconRepository
from .migrations import apply_database_migrations

def setup_database(db_path: str) -> PyTuple[sessionmaker, BeaconRepository]:
    """Setup database and return session factory and repository"""
    # Apply any pending migrations before creating tables
    try:
        migrations_applied = apply_database_migrations(db_path)
        if migrations_applied:
            logging.info(f"Applied database migrations: {', '.join(migrations_applied)}")
    except Exception as e:
        logging.error(f"Error applying database migrations: {e}")
        # Continue anyway - create_all will handle new databases

    engine = create_engine(f'sqlite:///{db_path}')
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal, BeaconRepository(SessionLocal)