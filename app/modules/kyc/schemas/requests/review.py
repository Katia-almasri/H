"""KYC review request schema."""

from typing import Optional
from pydantic import BaseModel, Field


class KYCReviewRequest(BaseModel):
    tier: Optional[str] = Field(None, description="KYC tier to assign (basic or full). Required for approval.")
    notes: Optional[str] = Field(None, max_length=2000)
