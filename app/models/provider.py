"""Provider database model."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from app.database.database import Base


class Provider(Base):
    """Provider model for storing LLM API provider information."""

    __tablename__ = "providers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    base_url = Column(String, nullable=False)
    api_key_encrypted = Column(String, nullable=False)
    channel_type = Column(String, nullable=False, default="openai")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_fetched_at = Column(DateTime, nullable=True)
