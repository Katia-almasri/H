"""KYC submission response schema."""

from typing import Optional
from datetime import date, datetime
from pydantic import BaseModel


class KYCSubmissionResponse(BaseModel):
    id: str
    user_id: str
    full_legal_name: str
    date_of_birth: date
    nationality: str
    country_of_residence: str
    residential_address: str
    source_of_funds: str
    source_of_funds_details: Optional[str]
    is_pep: bool
    status: str
    tier: str
    reviewed_by: Optional[str]
    review_notes: Optional[str]
    reviewed_at: Optional[datetime]
    submitted_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}
