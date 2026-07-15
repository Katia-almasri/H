"""KYC response schemas."""

from app.modules.kyc.schemas.responses.submission import KYCSubmissionResponse
from app.modules.kyc.schemas.responses.document import KYCDocumentResponse
from app.modules.kyc.schemas.responses.admin_submission import (
    AdminKYCSubmissionItemResponse,
    AdminKYCSubmissionListResponse,
)
from app.modules.kyc.schemas.responses.admin_submission_detail import (
    AdminKYCDocumentResponse,
    AdminKYCInvestorDetailResponse,
    AdminKYCSubmissionDetailResponse,
)
from app.modules.kyc.schemas.responses.metrics import KYCMetricsResponse

__all__ = [
    "KYCSubmissionResponse",
    "KYCDocumentResponse",
    "AdminKYCSubmissionItemResponse",
    "AdminKYCSubmissionListResponse",
    "AdminKYCDocumentResponse",
    "AdminKYCInvestorDetailResponse",
    "AdminKYCSubmissionDetailResponse",
    "KYCMetricsResponse",
]
