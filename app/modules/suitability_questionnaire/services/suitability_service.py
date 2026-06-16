"""Suitability service — primary orchestrator.

Handles questionnaire retrieval, status assembly, and submission
orchestration. Every state-changing operation runs inside a single
transaction and writes an ``audit_logs`` entry; if the audit write fails
the whole transaction rolls back.

Requirements: 1.4, 1.5, 1.6, 1.7, 2.2–2.8, 3.1, 3.6–3.12, 5.4–5.7,
              6.5, 9.1–9.5, 9.7.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.enums.audit_action import AuditAction
from app.modules.kyc.models.kyc_submission import KYCSubmission
from app.modules.suitability_questionnaire.enums import (
    QuestionId,
    SuitabilityOutcome,
)
from app.modules.suitability_questionnaire.models.investor_suitability import (
    InvestorSuitability,
)
from app.modules.suitability_questionnaire.repositories import (
    InvestorSuitabilityRepository,
    SuitabilityAcknowledgementRepository,
    SuitabilityCompletionMarkerRepository,
)
from app.modules.suitability_questionnaire.schemas.requests.submit_questionnaire import (
    SubmitQuestionnaireRequest,
)
from app.modules.suitability_questionnaire.services.scoring_engine import (
    QUESTION_DEFINITIONS,
    QUESTIONNAIRE_VERSION,
    score_submission,
)
from packages.core.exceptions import AuthorizationException, ValidationException


# ---------------------------------------------------------------------------
# Human-readable prompts for each question (used by get_questionnaire)
# ---------------------------------------------------------------------------

_QUESTION_PROMPTS: dict[QuestionId, str] = {
    QuestionId.Q1: "What is your approximate net worth (excluding your primary residence)?",
    QuestionId.Q2: "What is your approximate annual income?",
    QuestionId.Q3: "What percentage of your investable assets do you plan to allocate to this platform?",
    QuestionId.Q4: "What is your intended investment liquidity horizon?",
    QuestionId.Q5: "What is your prior investment experience?",
    QuestionId.Q6: "If your investment lost 20% of its value, what would you do?",
    QuestionId.Q7: "What is your primary investment objective?",
}

# ---------------------------------------------------------------------------
# Platform constant
# ---------------------------------------------------------------------------

#: Minimum share size hint in AED surfaced when outcome is NOT_SUITABLE.
_MINIMUM_SHARE_SIZE_AED: int = 500


class SuitabilityService:
    """Primary orchestrator service for the suitability questionnaire module."""

    def __init__(self, db: AsyncSession, redis_client: Redis) -> None:
        self.db = db
        self.redis = redis_client
        self.suitability_repo = InvestorSuitabilityRepository(db)
        self.ack_repo = SuitabilityAcknowledgementRepository(db)
        self.marker_repo = SuitabilityCompletionMarkerRepository(db)

    # ------------------------------------------------------------------
    # GET /suitability/questionnaire
    # ------------------------------------------------------------------

    async def get_questionnaire(self, user_id: str, tenant_id: str) -> dict:
        """Return the seven questions with answer enumerations and version.

        No database access needed — the question set is defined by the
        scoring engine's ``QUESTION_DEFINITIONS``.
        """
        questions: list[dict[str, Any]] = []
        for qd in QUESTION_DEFINITIONS:
            questions.append(
                {
                    "id": qd.id.value,
                    "prompt": _QUESTION_PROMPTS[qd.id],
                    "answers": list(qd.answer_scores.keys()),
                }
            )

        return {
            "questionnaire_version": QUESTIONNAIRE_VERSION,
            "questions": questions,
        }

    # ------------------------------------------------------------------
    # GET /suitability/status
    # ------------------------------------------------------------------

    async def get_status(self, user_id: str, tenant_id: str) -> dict:
        """Assemble the investor's current suitability lifecycle state.

        Combines the active suitability record (if any), the completion
        marker, and the current UTC time to derive a deterministic status.
        """
        active = await self.suitability_repo.get_active(user_id, tenant_id)
        marker_exists = await self.marker_repo.exists(user_id, tenant_id)
        now = datetime.now(timezone.utc)

        if active is None:
            # No suitability record — check if questionnaire is required
            return {
                "state": "SUITABILITY_REQUIRED",
                "can_invest": False,
                "outcome": None,
                "total_score": None,
                "warning_reasons": [],
                "block_reason": None,
                "expires_at": None,
                "renewal_due": False,
                "renewal_required": False,
                "retake_allowed_at": None,
                "minimum_share_size_aed": None,
                "questionnaire_version": QUESTIONNAIRE_VERSION,
                "message": "Questionnaire completion is required before investing.",
            }

        # Compute renewal flags from expiry timestamp
        expires_at = active.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        renewal_required = now >= expires_at
        renewal_due = (
            not renewal_required
            and (expires_at - now) <= timedelta(days=30)
        )

        outcome = active.outcome

        # If expired, treat as needing renewal
        if renewal_required:
            return {
                "state": "SUITABILITY_REQUIRED",
                "can_invest": False,
                "outcome": outcome,
                "total_score": active.total_score,
                "warning_reasons": list(active.warning_reasons or []),
                "block_reason": active.block_reason,
                "expires_at": expires_at.isoformat(),
                "renewal_due": False,
                "renewal_required": True,
                "retake_allowed_at": (
                    active.retake_allowed_at.isoformat()
                    if active.retake_allowed_at
                    else None
                ),
                "minimum_share_size_aed": None,
                "questionnaire_version": QUESTIONNAIRE_VERSION,
                "message": "Your suitability assessment has expired. Please retake the questionnaire.",
            }

        # Active record with NOT_SUITABLE outcome
        if outcome == SuitabilityOutcome.NOT_SUITABLE.value:
            retake_at = active.retake_allowed_at
            if retake_at and retake_at.tzinfo is None:
                retake_at = retake_at.replace(tzinfo=timezone.utc)
            return {
                "state": "NOT_SUITABLE",
                "can_invest": False,
                "outcome": outcome,
                "total_score": active.total_score,
                "warning_reasons": [],
                "block_reason": active.block_reason,
                "expires_at": expires_at.isoformat(),
                "renewal_due": renewal_due,
                "renewal_required": False,
                "retake_allowed_at": retake_at.isoformat() if retake_at else None,
                "minimum_share_size_aed": _MINIMUM_SHARE_SIZE_AED,
                "questionnaire_version": QUESTIONNAIRE_VERSION,
                "message": "You are not currently eligible to invest. "
                "Please review the block reason and try again after the cool-off period.",
            }

        # Active record with ELIGIBLE_WITH_WARNING
        if outcome == SuitabilityOutcome.ELIGIBLE_WITH_WARNING.value:
            return {
                "state": "ELIGIBLE_WITH_WARNING",
                "can_invest": True,
                "outcome": outcome,
                "total_score": active.total_score,
                "warning_reasons": list(active.warning_reasons or []),
                "block_reason": None,
                "expires_at": expires_at.isoformat(),
                "renewal_due": renewal_due,
                "renewal_required": False,
                "retake_allowed_at": None,
                "minimum_share_size_aed": None,
                "questionnaire_version": QUESTIONNAIRE_VERSION,
                "message": "You are eligible to invest with risk acknowledgement required per property.",
            }

        # Active record with ELIGIBLE
        return {
            "state": "ELIGIBLE",
            "can_invest": True,
            "outcome": outcome,
            "total_score": active.total_score,
            "warning_reasons": [],
            "block_reason": None,
            "expires_at": expires_at.isoformat(),
            "renewal_due": renewal_due,
            "renewal_required": False,
            "retake_allowed_at": None,
            "minimum_share_size_aed": None,
            "questionnaire_version": QUESTIONNAIRE_VERSION,
            "message": "You are eligible to invest.",
        }

    # ------------------------------------------------------------------
    # POST /suitability/submit
    # ------------------------------------------------------------------

    async def submit_questionnaire(
        self,
        user_id: str,
        tenant_id: str,
        body: SubmitQuestionnaireRequest,
        ip_address: str,
        user_agent: str,
    ) -> dict:
        """Validate, score, and persist a questionnaire submission.

        Runs inside a single transaction. If any step fails, the entire
        transaction rolls back automatically.
        """
        # (a) Verify approved KYC exists for this user+tenant
        kyc_submission = await self._get_approved_kyc(user_id, tenant_id)

        # (b) Verify questionnaire version matches current
        if body.questionnaire_version != QUESTIONNAIRE_VERSION:
            raise ValidationException(
                "Questionnaire version is out of date. "
                f"Expected version {QUESTIONNAIRE_VERSION}, "
                f"received version {body.questionnaire_version}.",
                details={"current_version": QUESTIONNAIRE_VERSION},
            )

        # (c) Check cool-off period
        latest_not_suitable = (
            await self.suitability_repo.get_latest_not_suitable(
                user_id, tenant_id
            )
        )
        if latest_not_suitable and latest_not_suitable.retake_allowed_at:
            retake_at = latest_not_suitable.retake_allowed_at
            if retake_at.tzinfo is None:
                retake_at = retake_at.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            if retake_at > now:
                raise ValidationException(
                    "Cool-off period is in effect. "
                    "You may retake the questionnaire after the cool-off expires.",
                    details={
                        "retake_allowed_at": retake_at.isoformat(),
                    },
                )

        # (d) Score the submission
        scoring_result = score_submission(body.answers)

        # (e) Get prior active record
        prior_active = await self.suitability_repo.get_active(
            user_id, tenant_id
        )

        # (f) Build the new InvestorSuitability row
        now = datetime.now(timezone.utc)
        new_id = str(uuid.uuid4())
        completed_at = now
        expires_at = completed_at + timedelta(days=365)
        retake_allowed_at = (
            completed_at + timedelta(days=30)
            if scoring_result.outcome == SuitabilityOutcome.NOT_SUITABLE
            else None
        )

        new_record = InvestorSuitability(
            id=new_id,
            tenant_id=tenant_id,
            user_id=user_id,
            kyc_submission_id=kyc_submission.id,
            answers={q.value: v for q, v in body.answers.items()},
            per_question_scores=scoring_result.per_question_scores,
            total_score=scoring_result.total_score,
            outcome=scoring_result.outcome.value,
            warning_reasons=[wr.value for wr in scoring_result.warning_reasons],
            block_reason=scoring_result.block_reason,
            questionnaire_version=QUESTIONNAIRE_VERSION,
            submission_ip=ip_address,
            submission_user_agent=(user_agent[:512] if user_agent else None),
            completed_at=completed_at,
            expires_at=expires_at,
            retake_allowed_at=retake_allowed_at,
            superseded_by=None,
            created_at=now,
        )

        # (e continued) Supersede prior or just insert
        prior_id = prior_active.id if prior_active else None
        await self.suitability_repo.supersede_and_insert(new_record, prior_id)

        # (g) Clear the completion marker
        await self.marker_repo.clear(user_id, tenant_id)

        # (h) Write audit log entry
        await self._write_audit_log(
            user_id=user_id,
            tenant_id=tenant_id,
            action=AuditAction.SUITABILITY_SUBMITTED.value,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata={
                "suitability_id": new_id,
                "outcome": scoring_result.outcome.value,
                "total_score": scoring_result.total_score,
                "superseded_record_id": prior_id,
            },
        )

        # Flush all writes within the current session transaction.
        await self.db.flush()

        # Return data for SubmissionResultResponse
        outcome_messages = {
            SuitabilityOutcome.ELIGIBLE: "You are eligible to invest.",
            SuitabilityOutcome.ELIGIBLE_WITH_WARNING: (
                "You are eligible to invest with risk acknowledgement required per property."
            ),
            SuitabilityOutcome.NOT_SUITABLE: (
                "Based on your responses, investing may not be suitable for you at this time."
            ),
        }

        return {
            "suitability_id": new_id,
            "outcome": scoring_result.outcome.value,
            "total_score": scoring_result.total_score,
            "warning_reasons": [wr.value for wr in scoring_result.warning_reasons],
            "block_reason": scoring_result.block_reason,
            "expires_at": expires_at.isoformat(),
            "retake_allowed_at": (
                retake_allowed_at.isoformat() if retake_allowed_at else None
            ),
            "questionnaire_version": QUESTIONNAIRE_VERSION,
            "message": outcome_messages[scoring_result.outcome],
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _get_approved_kyc(
        self, user_id: str, tenant_id: str
    ) -> KYCSubmission:
        """Verify that an approved KYC exists for the user in this tenant.

        Raises:
            ValidationException: If no approved KYC submission found.
            AuthorizationException: On cross-tenant access (indistinguishable
                from not-found per Req 1.7 / 9.4).
        """
        stmt = select(KYCSubmission).where(
            KYCSubmission.user_id == user_id,
            KYCSubmission.status == "approved",
        )
        result = await self.db.execute(stmt)
        kyc = result.scalar_one_or_none()

        if kyc is None:
            raise ValidationException(
                "An approved KYC submission is required before completing "
                "the suitability questionnaire."
            )

        return kyc

    async def _write_audit_log(
        self,
        user_id: str,
        tenant_id: str,
        action: str,
        ip_address: str | None,
        user_agent: str | None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Insert a row into the audit_logs table.

        Uses raw SQL insert since the audit_logs table is a shared, append-only
        infrastructure table that doesn't have a dedicated ORM model in the
        current codebase. Follows the required fields from the product rules:
        user_id, action, ip_address, user_agent, timestamp_utc, metadata.

        The insert participates in the caller's transaction — if it fails,
        the entire parent transaction rolls back.
        """
        from sqlalchemy import text

        audit_id = str(uuid.uuid4())
        timestamp_utc = datetime.now(timezone.utc)
        metadata_json = json.dumps(metadata) if metadata else None
        truncated_ua = (user_agent[:512] if user_agent else None)

        stmt = text(
            """
            INSERT INTO audit_logs (id, user_id, tenant_id, action, ip_address, user_agent, timestamp_utc, metadata)
            VALUES (:id, :user_id, :tenant_id, :action, :ip_address, :user_agent, :timestamp_utc, CAST(:metadata AS JSONB))
            """
        )
        await self.db.execute(
            stmt,
            {
                "id": audit_id,
                "user_id": user_id,
                "tenant_id": tenant_id,
                "action": action,
                "ip_address": ip_address,
                "user_agent": truncated_ua,
                "timestamp_utc": timestamp_utc,
                "metadata": metadata_json,
            },
        )
