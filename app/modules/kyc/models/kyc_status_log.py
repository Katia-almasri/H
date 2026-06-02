"""KYC status transition log — append-only."""

from sqlalchemy import Column, String, DateTime
from datetime import datetime

from app.database import Base


class KYCStatusLog(Base):
    """Append-only log of KYC status transitions."""
    __tablename__ = "kyc_status_logs"

    id = Column(String, primary_key=True)
    submission_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    from_status = Column(String, nullable=False)
    to_status = Column(String, nullable=False)
    changed_by = Column(String, nullable=True)  # admin user_id or "system"
    notes = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
