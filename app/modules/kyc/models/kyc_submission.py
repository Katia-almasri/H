"""KYC submission model."""

from sqlalchemy import Column, String, Boolean, DateTime, Date
from datetime import datetime

from app.database import Base


class KYCSubmission(Base):
    """Investor KYC submission data."""
    __tablename__ = "kyc_submissions"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)

    # Personal information
    full_legal_name = Column(String, nullable=False)
    date_of_birth = Column(Date, nullable=False)
    nationality = Column(String, nullable=False)
    country_of_residence = Column(String, nullable=False)
    residential_address = Column(String, nullable=False)

    # Source of funds
    source_of_funds = Column(String, nullable=False)  # SourceOfFunds enum value
    source_of_funds_details = Column(String, nullable=True)  # Free text

    # PEP declaration
    is_pep = Column(Boolean, default=False, nullable=False)

    # Status
    status = Column(String, default="not_submitted", nullable=False)  # KYCStatus
    tier = Column(String, default="unverified", nullable=False)  # KYCTier

    # Review
    reviewed_by = Column(String, nullable=True)
    review_notes = Column(String, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    # Timestamps
    submitted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
