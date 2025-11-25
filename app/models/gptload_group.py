"""GPTLoad group database model."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, CheckConstraint
from app.database.database import Base


class GPTLoadGroup(Base):
    """Model for tracking GPT-Load groups created by the system."""

    __tablename__ = "gptload_groups"

    id = Column(Integer, primary_key=True, index=True)
    gptload_group_id = Column(Integer, nullable=False, unique=True)
    name = Column(String, nullable=False, unique=True)
    group_type = Column(String, nullable=False)  # standard or aggregate
    provider_id = Column(Integer, ForeignKey("providers.id", ondelete="CASCADE"), nullable=True, index=True)
    normalized_model = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_sync_timestamp = Column(DateTime, nullable=True)
    config_hash = Column(String, nullable=True)

    # Constraints
    __table_args__ = (
        CheckConstraint("group_type IN ('standard', 'aggregate')", name='ck_group_type'),
    )
