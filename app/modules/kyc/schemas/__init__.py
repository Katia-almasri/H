"""KYC schemas."""

from app.modules.kyc.schemas.requests import KYCSubmitRequest, KYCReviewRequest
from app.modules.kyc.schemas.responses import KYCSubmissionResponse, KYCDocumentResponse

__all__ = ["KYCSubmitRequest", "KYCReviewRequest", "KYCSubmissionResponse", "KYCDocumentResponse"]
