"""KYC router — investor submission + admin review + reference data lookups."""

from datetime import date, datetime
from math import ceil
from typing import Annotated, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request, UploadFile, File, Form, Query
from fastapi.responses import FileResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.status import HTTP_201_CREATED

from app.database import get_db
from app.redis_client import get_redis
from app.modules.auth.enums import UserRole
from app.modules.auth.schemas.responses.user import UserResponse
from app.modules.kyc.enums import KYCMetricPeriod
from app.modules.kyc.services import KYCService, KYCMetricsService
from app.modules.kyc.services.lookups import (
    get_document_types,
    get_allowed_residence_countries,
    get_source_of_funds,
    get_allowed_nationalities,
    get_kyc_status as get_kyc_status_lookup,
    get_kyc_tiers,
)
from app.modules.kyc.schemas import (
    KYCSubmitRequest,
    KYCReviewRequest,
    AdminKYCDocumentResponse,
    AdminKYCInvestorDetailResponse,
    AdminKYCSubmissionDetailResponse,
    AdminKYCSubmissionItemResponse,
    AdminKYCSubmissionListResponse,
    KYCMetricsResponse,
    KYCSubmissionResponse,
    KYCDocumentResponse,
)
from packages.auth.dependencies import RoleChecker
from packages.core.exceptions import (
    ValidationException,
    NotFoundException,
)
from packages.core.i18n import t
from packages.core.response import api_response

router = APIRouter(prefix="/kyc", tags=["KYC"])

# ── Role-based dependencies ───────────────────────────────────────────────────
require_investor = RoleChecker(allowed_roles=[UserRole.INVESTOR])
require_admin = RoleChecker(allowed_roles=[UserRole.ADMIN])


# ── Dependencies ──────────────────────────────────────────────────────────────

def get_kyc_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[Redis, Depends(get_redis)],
) -> KYCService:
    return KYCService(db, redis_client)


def get_kyc_metrics_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> KYCMetricsService:
    return KYCMetricsService(db)


# ══════════════════════════════════════════════════════════════════════════════
# REFERENCE DATA (public — no auth required)
# ══════════════════════════════════════════════════════════════════════════════


@router.get("/lookups/document-types", summary="List KYC document types")
async def list_document_types():
    """Return all supported KYC document types (value + human-readable label)."""
    return api_response(
        message=t("api.kyc.lookups.document_types.retrieved"),
        data=get_document_types(),
    )


@router.get("/lookups/residence-countries", summary="List allowed residence countries")
async def list_residence_countries():
    """Return all countries where investors are allowed to reside (ISO code + name)."""
    return api_response(
        message=t("api.kyc.lookups.residence_countries.retrieved"),
        data=get_allowed_residence_countries(),
    )


@router.get("/lookups/source-of-funds", summary="List source-of-funds options")
async def list_source_of_funds():
    """Return all accepted source-of-funds options (value + human-readable label)."""
    return api_response(
        message=t("api.kyc.lookups.source_of_funds.retrieved"),
        data=get_source_of_funds(),
    )


@router.get("/lookups/nationalities", summary="List allowed nationalities")
async def list_nationalities():
    """Return all nationalities not subject to sanctions or regulatory restrictions."""
    return api_response(
        message=t("api.kyc.lookups.nationalities.retrieved"),
        data=get_allowed_nationalities(),
    )


@router.get("/lookups/statuses", summary="List KYC statuses")
async def list_kyc_statuses():
    """Return all available KYC submission statuses."""
    return api_response(
        message=t("api.kyc.lookups.statuses.retrieved"),
        data=get_kyc_status_lookup(),
    )


@router.get("/lookups/tiers", summary="List KYC tiers")
async def list_kyc_tiers():
    """Return all available KYC verification tiers."""
    return api_response(
        message=t("api.kyc.lookups.tiers.retrieved"),
        data=get_kyc_tiers(),
    )


# ══════════════════════════════════════════════════════════════════════════════
# INVESTOR ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════


@router.post("/submit", summary="Submit KYC data")
async def submit_kyc(
    body: KYCSubmitRequest,
    user_id: Annotated[str, Depends(require_investor)],
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
    user_id: Annotated[str, Depends(require_investor)],
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
    user_id: Annotated[str, Depends(require_investor)],
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


@router.get("/admin/metrics", summary="Get KYC metrics")
async def get_kyc_metrics(
    user_id: Annotated[str, Depends(require_admin)],
    metrics_service: Annotated[KYCMetricsService, Depends(get_kyc_metrics_service)],
    period: Annotated[KYCMetricPeriod, Query()] = KYCMetricPeriod.DAY,
    reference_date: Annotated[Optional[date], Query()] = None,
):
    """Admin gets KYC operational metrics for a selected date period."""
    response: KYCMetricsResponse = await metrics_service.get_metrics(
        period=period,
        reference_date=reference_date or datetime.utcnow().date(),
    )
    return api_response(
        message="KYC metrics retrieved.",
        data=response.model_dump(),
    )


@router.get("/admin/submissions", summary="List KYC submissions for admin")
async def list_kyc_submissions_for_admin(
    user_id: Annotated[str, Depends(require_admin)],
    kyc_service: Annotated[KYCService, Depends(get_kyc_service)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    search: Annotated[Optional[str], Query(min_length=1, max_length=100)] = None,
    nationality: Annotated[Optional[str], Query(min_length=2, max_length=100)] = None,
    tier: Optional[str] = None,
    submitted_from: Optional[datetime] = None,
    submitted_to: Optional[datetime] = None,
    order_by: str = "submitted_at",
    order_direction: str = "desc",
    status: Optional[str] = None,
):
    """Admin lists KYC submissions with filters, ordering, and pagination."""
    try:
        rows, total = await kyc_service.get_kyc_submissions_for_admin(
            page=page,
            page_size=page_size,
            search=search,
            nationality=nationality,
            tier=tier,
            status=status,
            submitted_from=submitted_from,
            submitted_to=submitted_to,
            order_by=order_by,
            order_direction=order_direction,
        )
    except ValueError as e:
        raise ValidationException(str(e))

    items = [
        AdminKYCSubmissionItemResponse(
            investor=UserResponse.model_validate(investor),
            kyc=KYCSubmissionResponse.model_validate(submission),
        )
        for submission, investor in rows
    ]
    response = AdminKYCSubmissionListResponse(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        total_pages=ceil(total / page_size) if total else 0,
    )

    return api_response(
        message="KYC submissions retrieved.",
        data=response.model_dump(),
    )


@router.get("/admin/submissions/{submission_id}", summary="Get KYC submission details")
async def get_kyc_submission_details_for_admin(
    submission_id: str,
    request: Request,
    user_id: Annotated[str, Depends(require_admin)],
    kyc_service: Annotated[KYCService, Depends(get_kyc_service)],
):
    """Admin gets one KYC submission with investor profile and uploaded documents."""
    try:
        submission, investor, documents = await kyc_service.get_kyc_submission_detail_for_admin(
            submission_id
        )
    except ValueError as e:
        raise NotFoundException(str(e))

    documents_base_url = str(
        request.url_for(
            "view_kyc_document_by_file_name_for_admin",
            file_name="__file_name__",
        )
    ).replace("__file_name__", "")

    response = AdminKYCSubmissionDetailResponse(
        investor=AdminKYCInvestorDetailResponse(
            id=investor.id,
            full_name=investor.full_name,
            username=investor.username,
            email=investor.email,
            phone_number=investor.phone_number,
            full_legal_name=submission.full_legal_name,
            date_of_birth=submission.date_of_birth,
        ),
        kyc=KYCSubmissionResponse.model_validate(submission),
        documents_base_url=documents_base_url,
        documents=[
            AdminKYCDocumentResponse(
                **KYCDocumentResponse.model_validate(document).model_dump(),
                file_url=f"{documents_base_url}{quote(document.file_name, safe='')}",
                view_url=str(
                    request.url_for(
                        "view_kyc_document_for_admin",
                        document_id=document.id,
                    )
                ),
            )
            for document in documents
        ],
    )

    return api_response(
        message="KYC submission details retrieved.",
        data=response.model_dump(),
    )


@router.get("/admin/documents/files/{file_name}", summary="View KYC document by file name")
async def view_kyc_document_by_file_name_for_admin(
    file_name: str,
    user_id: Annotated[str, Depends(require_admin)],
    kyc_service: Annotated[KYCService, Depends(get_kyc_service)],
):
    """Admin streams a KYC document file by file name for review."""
    try:
        document, file_path = await kyc_service.get_document_file_by_name_for_admin(file_name)
    except ValueError as e:
        raise NotFoundException(str(e))

    return FileResponse(
        path=file_path,
        media_type=document.content_type,
        filename=document.file_name,
        content_disposition_type="inline",
    )


@router.get("/admin/documents/{document_id}/view", summary="View KYC document")
async def view_kyc_document_for_admin(
    document_id: str,
    user_id: Annotated[str, Depends(require_admin)],
    kyc_service: Annotated[KYCService, Depends(get_kyc_service)],
):
    """Admin streams a KYC document file inline for review."""
    try:
        document, file_path = await kyc_service.get_document_file_for_admin(document_id)
    except ValueError as e:
        raise NotFoundException(str(e))

    return FileResponse(
        path=file_path,
        media_type=document.content_type,
        filename=document.file_name,
        content_disposition_type="inline",
    )


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
