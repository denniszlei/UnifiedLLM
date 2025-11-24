"""Sync record database model."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, CheckConstraint
from app.database.database import Base


class SyncRecord(Base):
    """Model for tracking configuration sync history."""

    __tablename__ = "sync_records"

    id = Column(Integer, primary_key=True, index=True)
    status = Column(String, nullable=False)  # pending, in_progress, success, failed
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    changes_summary = Column(Text, nullable=True)

    # Constraints
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'in_progress', 'success', 'failed')", name='ck_sync_status'),
    )
