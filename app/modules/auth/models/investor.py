"""Investor profile model — linked to User table."""

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from datetime import datetime

from app.database import Base


class Investor(Base):
    """Investor-specific profile and 2FA state. One-to-one with User."""
    __tablename__ = "investors"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)

    # 2FA
    two_fa_enabled = Column(Boolean, default=False, nullable=False)
    two_fa_status = Column(String, default="disabled", nullable=False)
    totp_secret_encrypted = Column(String, nullable=True)
    recovery_codes_hash = Column(String, nullable=True)  # JSON string of hashes
    recovery_codes_remaining = Column(String, default="0", nullable=False)
    recovery_codes_acknowledged = Column(Boolean, default=False, nullable=False)
    re_enrollment_deadline = Column(DateTime, nullable=True)
    two_fa_enabled_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
