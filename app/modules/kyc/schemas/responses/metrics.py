"""KYC metrics response schemas."""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.modules.kyc.enums import KYCMetricPeriod


class KYCMetricsResponse(BaseModel):
    """Admin KYC metrics for a selected period."""

    period: KYCMetricPeriod
    reference_date: date
    period_start: datetime
    period_end: datetime
    total_submissions: int = Field(ge=0)
    approved_submissions: int = Field(ge=0)
    rejected_submissions: int = Field(ge=0)
    reviewed_submissions: int = Field(ge=0)
    approval_rate: float = Field(ge=0)
    rejection_rate: float = Field(ge=0)
    average_review_time_seconds: Optional[float] = Field(default=None, ge=0)
    average_review_time_hours: Optional[float] = Field(default=None, ge=0)
    pending_kyc_count: int = Field(ge=0)
