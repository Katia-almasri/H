"""Suitability questionnaire router.

Exposes five investor-facing endpoints under the ``/suitability`` prefix:

  GET  /suitability/questionnaire                       — fetch the 7 questions
  GET  /suitability/status                              — current lifecycle state
  POST /suitability/submit                              — submit answers
  GET  /suitability/properties/{property_id}/acknowledgement — check ack status
  POST /suitability/properties/{property_id}/acknowledge    — record ack

All routes:
  - Require a valid investor JWT (``require_investor`` role checker).
  - Resolve ``tenant_id`` via ``get_current_tenant()``.
  - Return responses via the ``api_response`` envelope.
  - Raise only ``AppException`` subclasses on failure.

Per FR-INV-023: the questionnaire must be completed after first KYC
approval and before the first investment is allowed. The ``GET
/suitability/questionnaire`` endpoint is the entry point for this flow —
the client fetches it after KYC approval is confirmed and presents the
questions to the investor before the investment screen is shown.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.status import HTTP_200_OK, HTTP_201_CREATED

from app.database import get_db
from app.modules.auth.enums import UserRole
from app.modules.suitability_questionnaire.schemas.requests import (
    AcknowledgeWarningRequest,
    SubmitQuestionnaireRequest,
)
from app.modules.suitability_questionnaire.services import (
    SuitabilityAcknowledgementService,
    SuitabilityService,
)
from app.redis_client import get_redis
from packages.auth.dependencies import RoleChecker
from packages.core.response import api_response

router = APIRouter(prefix="/suitability", tags=["Suitability"])

# ── Role dependency ───────────────────────────────────────────────────────────

require_investor = RoleChecker(allowed_roles=[UserRole.INVESTOR])


# ── Dependency factories ──────────────────────────────────────────────────────

def get_suitability_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[Redis, Depends(get_redis)],
) -> SuitabilityService:
    return SuitabilityService(db, redis_client)


def get_acknowledgement_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SuitabilityAcknowledgementService:
    return SuitabilityAcknowledgementService(db)


def _get_tenant_id(request: Request) -> str:
    """Resolve tenant from the X-Tenant-ID header (project convention)."""
    tenant_id = request.headers.get("X-Tenant-ID", "harvest-uae")
    return tenant_id


# ══════════════════════════════════════════════════════════════════════════════
# GET /suitability/questionnaire
# ══════════════════════════════════════════════════════════════════════════════


@router.get(
    "/questionnaire",
    summary="Fetch the suitability questionnaire",
    description=(
        "Returns the seven questions, their enumerated answer options, and the "
        "current questionnaire version. "
        "**Per FR-INV-023**: the investor must complete this questionnaire after "
        "first KYC approval and before any investment is allowed. The client "
        "should present this screen immediately upon receiving KYC approval "
        "notification."
    ),
)
async def get_questionnaire(
    request: Request,
    user_id: Annotated[str, Depends(require_investor)],
    service: Annotated[SuitabilityService, Depends(get_suitability_service)],
) -> dict:
    """Fetch the questionnaire questions and current version.

    - Triggered after first KYC approval (FR-INV-023).
    - The client calls this endpoint to render the questionnaire form.
    - Requires a valid investor JWT.
    """
    tenant_id = _get_tenant_id(request)
    data = await service.get_questionnaire(user_id=user_id, tenant_id=tenant_id)
    return api_response(
        message="Questionnaire fetched successfully.",
        data=data,
        code=HTTP_200_OK,
    )


# ══════════════════════════════════════════════════════════════════════════════
# GET /suitability/status
# ══════════════════════════════════════════════════════════════════════════════


@router.get(
    "/status",
    summary="Get suitability lifecycle status",
    description=(
        "Returns the investor's current suitability state, including outcome, "
        "score, expiry timestamps, renewal flags, and investment eligibility. "
        "Used by the investment screen to gate the buy button. "
        "When no questionnaire has been completed, returns "
        "``state=SUITABILITY_REQUIRED`` and ``can_invest=false``."
    ),
)
async def get_status(
    request: Request,
    user_id: Annotated[str, Depends(require_investor)],
    service: Annotated[SuitabilityService, Depends(get_suitability_service)],
) -> dict:
    """Return the investor's current suitability status."""
    tenant_id = _get_tenant_id(request)
    data = await service.get_status(user_id=user_id, tenant_id=tenant_id)
    return api_response(
        message="Suitability status retrieved.",
        data=data,
        code=HTTP_200_OK,
    )


# ══════════════════════════════════════════════════════════════════════════════
# POST /suitability/submit
# ══════════════════════════════════════════════════════════════════════════════


@router.post(
    "/submit",
    summary="Submit questionnaire answers",
    description=(
        "Accepts all seven answers plus the current questionnaire version. "
        "Scores the submission, persists the result, and returns the outcome "
        "(ELIGIBLE / ELIGIBLE_WITH_WARNING / NOT_SUITABLE). "
        "Rejects submissions if KYC is not approved, the version is stale, "
        "or the 30-day cool-off after NOT_SUITABLE is still active."
    ),
)
async def submit_questionnaire(
    request: Request,
    body: SubmitQuestionnaireRequest,
    user_id: Annotated[str, Depends(require_investor)],
    service: Annotated[SuitabilityService, Depends(get_suitability_service)],
) -> dict:
    """Submit a completed questionnaire.

    Processing (single DB transaction):
    1. Verify approved KYC exists for the investor.
    2. Verify ``questionnaire_version`` matches current engine version.
    3. Enforce the 30-day cool-off after a NOT_SUITABLE outcome.
    4. Score the answers → outcome + warnings/block reason.
    5. Supersede any prior active record and insert the new one.
    6. Clear the completion marker.
    7. Write a ``SUITABILITY_SUBMITTED`` audit log entry.

    If any step fails, the entire transaction rolls back.
    """
    tenant_id = _get_tenant_id(request)
    ip_address = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")

    data = await service.submit_questionnaire(
        user_id=user_id,
        tenant_id=tenant_id,
        body=body,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return api_response(
        message=data.get("message", "Questionnaire submitted."),
        data=data,
        code=HTTP_201_CREATED,
    )


# ══════════════════════════════════════════════════════════════════════════════
# GET /suitability/properties/{property_id}/acknowledgement
# ══════════════════════════════════════════════════════════════════════════════


@router.get(
    "/properties/{property_id}/acknowledgement",
    summary="Check warning acknowledgement status for a property",
    description=(
        "For investors with an ELIGIBLE_WITH_WARNING outcome, returns whether "
        "the risk warning for the specified property has already been "
        "acknowledged under the current active suitability record. "
        "The investment screen calls this before rendering the acknowledgement "
        "step."
    ),
)
async def get_acknowledgement_status(
    request: Request,
    property_id: str,
    user_id: Annotated[str, Depends(require_investor)],
    service: Annotated[SuitabilityAcknowledgementService, Depends(get_acknowledgement_service)],
) -> dict:
    """Return acknowledgement status for a property."""
    tenant_id = _get_tenant_id(request)
    data = await service.get_acknowledgement_status(
        user_id=user_id,
        tenant_id=tenant_id,
        property_id=property_id,
    )
    return api_response(
        message="Acknowledgement status retrieved.",
        data=data,
        code=HTTP_200_OK,
    )


# ══════════════════════════════════════════════════════════════════════════════
# POST /suitability/properties/{property_id}/acknowledge
# ══════════════════════════════════════════════════════════════════════════════


@router.post(
    "/properties/{property_id}/acknowledge",
    summary="Record risk warning acknowledgement for a property",
    description=(
        "Records that the investor has explicitly acknowledged the risk warning "
        "for the specified property under their current ELIGIBLE_WITH_WARNING "
        "suitability record. The operation is idempotent — submitting a second "
        "time returns the existing acknowledgement without creating a duplicate. "
        "Required before the investment screen allows a purchase for "
        "ELIGIBLE_WITH_WARNING investors."
    ),
)
async def acknowledge_warning(
    request: Request,
    property_id: str,
    _body: AcknowledgeWarningRequest,
    user_id: Annotated[str, Depends(require_investor)],
    service: Annotated[SuitabilityAcknowledgementService, Depends(get_acknowledgement_service)],
) -> dict:
    """Persist a risk-warning acknowledgement for a specific property."""
    tenant_id = _get_tenant_id(request)
    ip_address = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")

    data = await service.acknowledge(
        user_id=user_id,
        tenant_id=tenant_id,
        property_id=property_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return api_response(
        message="Risk warning acknowledged.",
        data=data,
        code=HTTP_201_CREATED,
    )
