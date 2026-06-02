"""KYC request schemas."""

from app.modules.kyc.schemas.requests.submit import KYCSubmitRequest
from app.modules.kyc.schemas.requests.review import KYCReviewRequest

__all__ = ["KYCSubmitRequest", "KYCReviewRequest"]
