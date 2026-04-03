"""
Database configuration and session management.
Sets up SQLAlchemy engine and session factory.
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from app.config import settings

# Create SQLAlchemy engine
# pool_pre_ping=True helps detect stale connections
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    # psycopg3 caches prepared statements server-side by default.
    # On hot-reload the old statements still exist on the connection,
    # causing DuplicatePreparedStatement errors. Disabling them here.
    connect_args={"prepare_threshold": None},
)

# Session factory for database operations
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency that provides a database session.
    Yields a session and ensures it's closed after the request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Initialize database by creating all tables.
    Called on application startup.
    """
    from app.models import User, StudentProfile, SupervisorProfile, Skill, Engagement, EngagementSkill, DeclaredSkill  # noqa: F401 - Import to register models
    Base.metadata.create_all(bind=engine)
