"""Model database model."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship, backref
from app.database.database import Base


class Model(Base):
    """Model for storing LLM model information."""

    __tablename__ = "models"

    id = Column(Integer, primary_key=True, index=True)
    provider_id = Column(Integer, ForeignKey("providers.id", ondelete="CASCADE"), nullable=False)
    original_name = Column(String, nullable=False)
    normalized_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    provider = relationship("Provider", backref=backref("models", cascade="all, delete-orphan", passive_deletes=True))

    # Constraints
    __table_args__ = (
        UniqueConstraint('provider_id', 'original_name', name='uq_provider_original_name'),
        Index('ix_models_provider_id', 'provider_id'),
        Index('ix_models_normalized_name', 'normalized_name'),
    )
