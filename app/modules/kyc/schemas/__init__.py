"""KYC schemas."""

from app.modules.kyc.schemas.requests import KYCSubmitRequest, KYCReviewRequest
from app.modules.kyc.schemas.responses import (
    AdminKYCDocumentResponse,
    AdminKYCInvestorDetailResponse,
    AdminKYCSubmissionDetailResponse,
    AdminKYCSubmissionItemResponse,
    AdminKYCSubmissionListResponse,
    KYCMetricsResponse,
    KYCSubmissionResponse,
    KYCDocumentResponse,
)

__all__ = [
    "KYCSubmitRequest",
    "KYCReviewRequest",
    "KYCSubmissionResponse",
    "KYCDocumentResponse",
    "AdminKYCDocumentResponse",
    "AdminKYCInvestorDetailResponse",
    "AdminKYCSubmissionDetailResponse",
    "AdminKYCSubmissionItemResponse",
    "AdminKYCSubmissionListResponse",
    "KYCMetricsResponse",
]
