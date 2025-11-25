"""Database migration utilities."""

import logging
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def migrate_database(db: Session) -> None:
    """Apply database migrations.
    
    This function checks for missing columns and adds them if needed.
    It's safe to call multiple times.
    
    Args:
        db: Database session.
    """
    logger.info("Checking for database migrations...")
    
    # Get database engine
    engine = db.get_bind()
    inspector = inspect(engine)
    
    # Migration 1: Add last_sync_timestamp and config_hash to gptload_groups
    if 'gptload_groups' in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('gptload_groups')]
        
        if 'last_sync_timestamp' not in columns:
            logger.info("Adding last_sync_timestamp column to gptload_groups table")
            try:
                db.execute(text(
                    "ALTER TABLE gptload_groups ADD COLUMN last_sync_timestamp DATETIME"
                ))
                db.commit()
                logger.info("Successfully added last_sync_timestamp column")
            except Exception as e:
                logger.error(f"Failed to add last_sync_timestamp column: {e}")
                db.rollback()
        
        if 'config_hash' not in columns:
            logger.info("Adding config_hash column to gptload_groups table")
            try:
                db.execute(text(
                    "ALTER TABLE gptload_groups ADD COLUMN config_hash VARCHAR"
                ))
                db.commit()
                logger.info("Successfully added config_hash column")
            except Exception as e:
                logger.error(f"Failed to add config_hash column: {e}")
                db.rollback()
    
    logger.info("Database migrations complete")


def get_migration_status(db: Session) -> dict:
    """Get the status of database migrations.
    
    Args:
        db: Database session.
        
    Returns:
        Dictionary with migration status information.
    """
    engine = db.get_bind()
    inspector = inspect(engine)
    
    status = {
        'tables': inspector.get_table_names(),
        'migrations_applied': []
    }
    
    # Check gptload_groups migrations
    if 'gptload_groups' in status['tables']:
        columns = [col['name'] for col in inspector.get_columns('gptload_groups')]
        
        if 'last_sync_timestamp' in columns:
            status['migrations_applied'].append('gptload_groups.last_sync_timestamp')
        
        if 'config_hash' in columns:
            status['migrations_applied'].append('gptload_groups.config_hash')
    
    return status
