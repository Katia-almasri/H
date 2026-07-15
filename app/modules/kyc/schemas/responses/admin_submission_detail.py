"""Admin KYC submission detail response schema."""

from datetime import date
from typing import Optional

from pydantic import BaseModel

from app.modules.kyc.schemas.responses.document import KYCDocumentResponse
from app.modules.kyc.schemas.responses.submission import KYCSubmissionResponse


class AdminKYCInvestorDetailResponse(BaseModel):
    id: str
    full_name: Optional[str]
    username: str
    email: str
    phone_number: Optional[str]
    full_legal_name: str
    date_of_birth: date


class AdminKYCDocumentResponse(KYCDocumentResponse):
    file_url: str
    view_url: str


class AdminKYCSubmissionDetailResponse(BaseModel):
    investor: AdminKYCInvestorDetailResponse
    kyc: KYCSubmissionResponse
    documents_base_url: str
    documents: list[AdminKYCDocumentResponse]
