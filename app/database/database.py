"""Database configuration and session management."""

import os
import logging
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

logger = logging.getLogger(__name__)

# Create data directory if it doesn't exist
os.makedirs("data", exist_ok=True)

# Create SQLAlchemy engine
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create declarative base for models
Base = declarative_base()


def get_db():
    """Get database session dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables.
    
    Creates all tables defined in the models if they don't exist.
    This function is idempotent and safe to call multiple times.
    """
    # Import all models to ensure they are registered with Base
    from app.models import Provider, Model, GPTLoadGroup, SyncRecord
    
    logger.info("Initializing database...")
    
    # Check if tables exist
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    
    if not existing_tables:
        logger.info("No existing tables found. Creating all tables...")
    else:
        logger.info(f"Found existing tables: {existing_tables}")
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    # Run migrations for existing databases
    if existing_tables:
        logger.info("Running database migrations...")
        from app.database.migrations import migrate_database
        db = SessionLocal()
        try:
            migrate_database(db)
        finally:
            db.close()
    
    # Verify tables were created
    inspector = inspect(engine)
    created_tables = inspector.get_table_names()
    logger.info(f"Database initialized with tables: {created_tables}")


def drop_all_tables():
    """Drop all tables from the database.
    
    WARNING: This will delete all data. Use only for testing or development.
    """
    logger.warning("Dropping all tables from database...")
    Base.metadata.drop_all(bind=engine)
    logger.info("All tables dropped successfully")


def reset_db():
    """Reset the database by dropping and recreating all tables.
    
    WARNING: This will delete all data. Use only for testing or development.
    """
    logger.warning("Resetting database...")
    drop_all_tables()
    init_db()
    logger.info("Database reset complete")
