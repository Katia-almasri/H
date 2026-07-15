"""Admin KYC submission list response schemas."""

from pydantic import BaseModel

from app.modules.auth.schemas.responses.user import UserResponse
from app.modules.kyc.schemas.responses.submission import KYCSubmissionResponse


class AdminKYCSubmissionItemResponse(BaseModel):
    investor: UserResponse
    kyc: KYCSubmissionResponse


class AdminKYCSubmissionListResponse(BaseModel):
    items: list[AdminKYCSubmissionItemResponse]
    page: int
    page_size: int
    total: int
    total_pages: int

