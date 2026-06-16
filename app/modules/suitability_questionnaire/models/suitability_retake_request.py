"""Suitability retake request model — NOT_SUITABLE recovery.

Created automatically when NOT_SUITABLE is recorded — drives the 30-day
countdown on the investor's dashboard.
"""

from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime

from app.database import Base


class SuitabilityRetakeRequest(Base):
    """Tracks the 30-day retake window after a NOT_SUITABLE outcome."""
    __tablename__ = "suitability_retake_requests"

    id = Column(UUID(as_uuid=False), primary_key=True)  # UUID

    user_id = Column(UUID(as_uuid=False), nullable=False)  # -> users.id
    previous_suitability_id = Column(
        UUID(as_uuid=False),
        ForeignKey("investor_suitability.id"),
        nullable=False,
    )  # -> investor_suitability.id

    requested_at = Column(DateTime(timezone=True), nullable=True)  # when user requested early retake (optional)
    allowed_at = Column(DateTime(timezone=True), nullable=True)  # computed = previous completed_at + 30 days

    status = Column(String, nullable=False)  # RetakeStatus enum value: PENDING | OPEN | COMPLETED

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
