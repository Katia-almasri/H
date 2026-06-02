"""KYC service — submission, document upload, and admin review."""

import os
import uuid
from datetime import datetime, date
from typing import Optional

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.kyc.enums import (
    KYCStatus,
    KYCTier,
    SourceOfFunds,
    DocumentType,
    AllowedFileType,
)
from app.modules.kyc.models.kyc_submission import KYCSubmission
from app.modules.kyc.models.kyc_document import KYCDocument
from app.modules.kyc.models.kyc_status_log import KYCStatusLog
from app.modules.kyc.repositories import (
    KYCSubmissionRepository,
    KYCDocumentRepository,
    KYCStatusLogRepository,
)
from app.modules.kyc.services.constraints_engine import (
    check_investor_eligibility,
    check_residence_country,
    validate_residential_address,
    check_nationality,
)

# File validation constants
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_CONTENT_TYPES = {t.value for t in AllowedFileType}
UPLOAD_DIR = "storage/kyc"


class KYCService:
    """Investor KYC submission and review service."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.submission_repo = KYCSubmissionRepository(db)
        self.document_repo = KYCDocumentRepository(db)
        self.status_log_repo = KYCStatusLogRepository(db)

    # ── Submission ────────────────────────────────────────────────────────────

    async def submit_kyc(
        self,
        user_id: str,
        full_legal_name: str,
        date_of_birth: date,
        nationality: str,
        country_of_residence: str,
        residential_address: str,
        source_of_funds: str,
        source_of_funds_details: Optional[str],
        is_pep: bool,
    ) -> KYCSubmission:
        """Create or update a KYC submission for an investor."""
        # Check for existing submission
        existing = await self.submission_repo.get_by_user_id(user_id)
        if existing and existing.status in (KYCStatus.PENDING.value, KYCStatus.UNDER_REVIEW.value):
            raise ValueError("A KYC submission is already pending review")

        # ── Constraint checks ─────────────────────────────────────────────────

        # Age eligibility (must be 21+)
        if not check_investor_eligibility(date_of_birth):
            raise ValueError("Investor must be at least 21 years old")

        # Nationality eligibility (sanctions check)
        is_allowed, nationality_msg = check_nationality(nationality)
        if not is_allowed:
            raise ValueError(nationality_msg)

        # Residence country eligibility
        is_allowed, country_msg = check_residence_country(country_of_residence)
        if not is_allowed:
            raise ValueError(country_msg)

        # Residential address validation
        is_valid, address_msg = validate_residential_address(residential_address, country_of_residence)
        if not is_valid:
            raise ValueError(address_msg)

        # Validate source_of_funds enum
        if source_of_funds not in [s.value for s in SourceOfFunds]:
            raise ValueError(f"Invalid source of funds: {source_of_funds}")

        submission = KYCSubmission(
            id=str(uuid.uuid4()),
            user_id=user_id,
            full_legal_name=full_legal_name,
            date_of_birth=date_of_birth,
            nationality=nationality,
            country_of_residence=country_of_residence,
            residential_address=residential_address,
            source_of_funds=source_of_funds,
            source_of_funds_details=source_of_funds_details,
            is_pep=is_pep,
            status=KYCStatus.PENDING.value,
            tier=KYCTier.UNVERIFIED.value,
            submitted_at=datetime.utcnow(),
        )

        submission = await self.submission_repo.create(submission)

        # Log status transition
        await self._log_status_change(
            submission_id=submission.id,
            user_id=user_id,
            from_status=KYCStatus.NOT_SUBMITTED.value,
            to_status=KYCStatus.PENDING.value,
            changed_by="system",
        )

        return submission

    async def get_submission(self, user_id: str) -> Optional[KYCSubmission]:
        """Get the latest KYC submission for a user."""
        return await self.submission_repo.get_by_user_id(user_id)

    # ── Document upload ───────────────────────────────────────────────────────

    async def upload_document(
        self,
        user_id: str,
        submission_id: str,
        document_type: str,
        file: UploadFile,
    ) -> KYCDocument:
        """Upload a KYC document with validation."""
        # Validate document type
        if document_type not in [d.value for d in DocumentType]:
            raise ValueError(f"Invalid document type: {document_type}")

        # Validate file type
        if file.content_type not in ALLOWED_CONTENT_TYPES:
            raise ValueError(
                f"Invalid file type: {file.content_type}. Allowed: JPEG, PNG, PDF"
            )

        # Read file content and validate size
        content = await file.read()
        if len(content) > MAX_FILE_SIZE_BYTES:
            raise ValueError(f"File too large. Maximum size is 10MB")

        # Verify submission belongs to user
        submission = await self.submission_repo.get_by_id(submission_id)
        if not submission or submission.user_id != user_id:
            raise ValueError("Submission not found")

        # Save file to local storage
        file_ext = self._get_extension(file.content_type)
        file_name = f"{uuid.uuid4()}{file_ext}"
        file_path = os.path.join(UPLOAD_DIR, user_id, file_name)

        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(content)

        # Create document record
        document = KYCDocument(
            id=str(uuid.uuid4()),
            submission_id=submission_id,
            user_id=user_id,
            document_type=document_type,
            file_name=file.filename or file_name,
            file_path=file_path,
            file_size=len(content),
            content_type=file.content_type,
        )

        return await self.document_repo.create(document)

    # ── Admin review ──────────────────────────────────────────────────────────

    async def approve_kyc(
        self,
        submission_id: str,
        admin_id: str,
        tier: str,
        notes: Optional[str] = None,
    ) -> KYCSubmission:
        """Admin approves a KYC submission and assigns a tier."""
        submission = await self.submission_repo.get_by_id(submission_id)
        if not submission:
            raise ValueError("Submission not found")

        if tier not in [t.value for t in KYCTier]:
            raise ValueError(f"Invalid tier: {tier}")

        old_status = submission.status
        submission.status = KYCStatus.APPROVED.value
        submission.tier = tier
        submission.reviewed_by = admin_id
        submission.review_notes = notes
        submission.reviewed_at = datetime.utcnow()
        submission.updated_at = datetime.utcnow()
        await self.submission_repo.update(submission)

        await self._log_status_change(
            submission_id=submission.id,
            user_id=submission.user_id,
            from_status=old_status,
            to_status=KYCStatus.APPROVED.value,
            changed_by=admin_id,
            notes=notes,
        )

        return submission

    async def reject_kyc(
        self,
        submission_id: str,
        admin_id: str,
        notes: Optional[str] = None,
    ) -> KYCSubmission:
        """Admin rejects a KYC submission."""
        submission = await self.submission_repo.get_by_id(submission_id)
        if not submission:
            raise ValueError("Submission not found")

        old_status = submission.status
        submission.status = KYCStatus.REJECTED.value
        submission.reviewed_by = admin_id
        submission.review_notes = notes
        submission.reviewed_at = datetime.utcnow()
        submission.updated_at = datetime.utcnow()
        await self.submission_repo.update(submission)

        await self._log_status_change(
            submission_id=submission.id,
            user_id=submission.user_id,
            from_status=old_status,
            to_status=KYCStatus.REJECTED.value,
            changed_by=admin_id,
            notes=notes,
        )

        return submission

    async def set_under_review(
        self, submission_id: str, admin_id: str
    ) -> KYCSubmission:
        """Admin marks a submission as under review."""
        submission = await self.submission_repo.get_by_id(submission_id)
        if not submission:
            raise ValueError("Submission not found")

        old_status = submission.status
        submission.status = KYCStatus.UNDER_REVIEW.value
        submission.updated_at = datetime.utcnow()
        await self.submission_repo.update(submission)

        await self._log_status_change(
            submission_id=submission.id,
            user_id=submission.user_id,
            from_status=old_status,
            to_status=KYCStatus.UNDER_REVIEW.value,
            changed_by=admin_id,
        )

        return submission

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _log_status_change(
        self,
        submission_id: str,
        user_id: str,
        from_status: str,
        to_status: str,
        changed_by: str,
        notes: Optional[str] = None,
    ) -> None:
        log = KYCStatusLog(
            id=str(uuid.uuid4()),
            submission_id=submission_id,
            user_id=user_id,
            from_status=from_status,
            to_status=to_status,
            changed_by=changed_by,
            notes=notes,
        )
        await self.status_log_repo.create(log)

    def _get_extension(self, content_type: str) -> str:
        ext_map = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "application/pdf": ".pdf",
        }
        return ext_map.get(content_type, ".bin")
