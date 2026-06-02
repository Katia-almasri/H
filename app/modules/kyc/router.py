"""KYC router — investor submission + admin review."""

from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.status import HTTP_201_CREATED

from app.database import get_db
from app.modules.auth.enums import UserRole
from app.modules.kyc.services import KYCService
from app.modules.kyc.schemas import (
    KYCSubmitRequest,
    KYCReviewRequest,
    KYCSubmissionResponse,
    KYCDocumentResponse,
)
from packages.auth.dependencies import get_current_user_id, RoleChecker
from packages.core.exceptions import (
    ValidationException,
    NotFoundException,
)
from packages.core.response import api_response

router = APIRouter(prefix="/kyc", tags=["KYC"])

# ── Role-based dependencies ───────────────────────────────────────────────────
require_admin = RoleChecker(allowed_roles=[UserRole.ADMIN])


# ── Dependencies ──────────────────────────────────────────────────────────────

def get_kyc_service(db: Annotated[AsyncSession, Depends(get_db)]) -> KYCService:
    return KYCService(db)


# ══════════════════════════════════════════════════════════════════════════════
# INVESTOR ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════


@router.post("/submit", summary="Submit KYC data")
async def submit_kyc(
    body: KYCSubmitRequest,
    user_id: Annotated[str, Depends(get_current_user_id)],
    kyc_service: Annotated[KYCService, Depends(get_kyc_service)],
):
    """Submit personal information for KYC verification."""
    try:
        submission = await kyc_service.submit_kyc(
            user_id=user_id,
            full_legal_name=body.full_legal_name,
            date_of_birth=body.date_of_birth,
            nationality=body.nationality,
            country_of_residence=body.country_of_residence,
            residential_address=body.residential_address,
            source_of_funds=body.source_of_funds,
            source_of_funds_details=body.source_of_funds_details,
            is_pep=body.is_pep,
        )
    except ValueError as e:
        raise ValidationException(str(e))

    return api_response(
        message="KYC submitted successfully. Pending review.",
        data=KYCSubmissionResponse.model_validate(submission).model_dump(),
        code=HTTP_201_CREATED,
    )


@router.post("/documents/upload", summary="Upload KYC document")
async def upload_document(
    user_id: Annotated[str, Depends(get_current_user_id)],
    kyc_service: Annotated[KYCService, Depends(get_kyc_service)],
    submission_id: str = Form(...),
    document_type: str = Form(...),
    file: UploadFile = File(...),
):
    """Upload a KYC document (JPEG, PNG, or PDF, max 10MB)."""
    try:
        document = await kyc_service.upload_document(
            user_id=user_id,
            submission_id=submission_id,
            document_type=document_type,
            file=file,
        )
    except ValueError as e:
        raise ValidationException(str(e))

    return api_response(
        message="Document uploaded successfully.",
        data=KYCDocumentResponse.model_validate(document).model_dump(),
        code=HTTP_201_CREATED,
    )


@router.get("/status", summary="Get KYC status")
async def get_kyc_status(
    user_id: Annotated[str, Depends(get_current_user_id)],
    kyc_service: Annotated[KYCService, Depends(get_kyc_service)],
):
    """Get the current KYC submission status for the authenticated investor."""
    submission = await kyc_service.get_submission(user_id)
    if not submission:
        return api_response(
            message="No KYC submission found.",
            data={"status": "not_submitted", "tier": "unverified"},
        )

    return api_response(
        message="KYC status retrieved.",
        data=KYCSubmissionResponse.model_validate(submission).model_dump(),
    )


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════


@router.post("/admin/review/{submission_id}/approve", summary="Approve KYC")
async def approve_kyc(
    submission_id: str,
    body: KYCReviewRequest,
    user_id: Annotated[str, Depends(require_admin)],
    kyc_service: Annotated[KYCService, Depends(get_kyc_service)],
):
    """Admin approves a KYC submission and assigns a tier."""
    if not body.tier:
        raise ValidationException("Tier is required for approval (basic or full)")

    try:
        submission = await kyc_service.approve_kyc(
            submission_id=submission_id,
            admin_id=user_id,
            tier=body.tier,
            notes=body.notes,
        )
    except ValueError as e:
        raise ValidationException(str(e))

    return api_response(
        message="KYC approved.",
        data=KYCSubmissionResponse.model_validate(submission).model_dump(),
    )


@router.post("/admin/review/{submission_id}/reject", summary="Reject KYC")
async def reject_kyc(
    submission_id: str,
    body: KYCReviewRequest,
    user_id: Annotated[str, Depends(require_admin)],
    kyc_service: Annotated[KYCService, Depends(get_kyc_service)],
):
    """Admin rejects a KYC submission."""
    try:
        submission = await kyc_service.reject_kyc(
            submission_id=submission_id,
            admin_id=user_id,
            notes=body.notes,
        )
    except ValueError as e:
        raise NotFoundException(str(e))

    return api_response(
        message="KYC rejected.",
        data=KYCSubmissionResponse.model_validate(submission).model_dump(),
    )


@router.post("/admin/review/{submission_id}/under-review", summary="Mark under review")
async def mark_under_review(
    submission_id: str,
    user_id: Annotated[str, Depends(require_admin)],
    kyc_service: Annotated[KYCService, Depends(get_kyc_service)],
):
    """Admin marks a submission as under review."""
    try:
        submission = await kyc_service.set_under_review(submission_id, user_id)
    except ValueError as e:
        raise NotFoundException(str(e))

    return api_response(
        message="KYC marked as under review.",
        data=KYCSubmissionResponse.model_validate(submission).model_dump(),
    )
