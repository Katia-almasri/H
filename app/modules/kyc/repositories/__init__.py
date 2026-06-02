"""KYC repositories."""

from app.modules.kyc.repositories.kyc_submission_repository import KYCSubmissionRepository
from app.modules.kyc.repositories.kyc_document_repository import KYCDocumentRepository
from app.modules.kyc.repositories.kyc_status_log_repository import KYCStatusLogRepository

__all__ = ["KYCSubmissionRepository", "KYCDocumentRepository", "KYCStatusLogRepository"]
