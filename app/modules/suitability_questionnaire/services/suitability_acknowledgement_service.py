"""Suitability acknowledgement service.

Handles per-property acknowledgement creation and status retrieval for
Investors with an ``ELIGIBLE_WITH_WARNING`` outcome. The repository uses
an idempotent insert (``ON CONFLICT DO NOTHING``) so a duplicate POST
returns the existing row without raising — satisfying Requirement 4.5.

Audit log entries are written within the same transaction as the
acknowledgement; if the audit write fails the entire transaction rolls
back and no acknowledgement is persisted (Requirements 4.10, 4.11).

Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.10, 4.11, 6.6, 9.1, 9.4.
"""

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.enums.audit_action import AuditAction
from app.modules.suitability_questionnaire.enums.suitability_outcome import (
    SuitabilityOutcome,
)
from app.modules.suitability_questionnaire.models.suitability_acknowledgement import (
    SuitabilityAcknowledgement,
)
from app.modules.suitability_questionnaire.repositories import (
    InvestorSuitabilityRepository,
    SuitabilityAcknowledgementRepository,
)
from packages.core.exceptions import ValidationException


class SuitabilityAcknowledgementService:
    """Per-property warning acknowledgement lifecycle."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.suitability_repo = InvestorSuitabilityRepository(db)
        self.ack_repo = SuitabilityAcknowledgementRepository(db)

    # ── Public methods ────────────────────────────────────────────────────────

    async def get_acknowledgement_status(
        self,
        user_id: str,
        tenant_id: str,
        property_id: str,
    ) -> dict[str, Any]:
        """Return acknowledgement status for a given property.

        If no active record exists or the outcome is not
        ``ELIGIBLE_WITH_WARNING``, returns a default "not acknowledged"
        response with empty warning reasons.
        """
        active_record = await self.suitability_repo.get_active(user_id, tenant_id)

        if (
            active_record is None
            or active_record.outcome != SuitabilityOutcome.ELIGIBLE_WITH_WARNING
        ):
            return {
                "acknowledged": False,
                "acknowledgement_id": None,
                "property_id": property_id,
                "warning_reasons": [],
                "acknowledged_at": None,
            }

        # Check whether an acknowledgement already exists for this property.
        ack = await self.ack_repo.get(
            suitability_id=active_record.id,
            user_id=user_id,
            property_id=property_id,
            tenant_id=tenant_id,
        )

        if ack is not None:
            return {
                "acknowledged": True,
                "acknowledgement_id": ack.id,
                "property_id": property_id,
                "warning_reasons": list(active_record.warning_reasons or []),
                "acknowledged_at": ack.acknowledged_at,
            }

        return {
            "acknowledged": False,
            "acknowledgement_id": None,
            "property_id": property_id,
            "warning_reasons": list(active_record.warning_reasons or []),
            "acknowledged_at": None,
        }

    async def acknowledge(
        self,
        user_id: str,
        tenant_id: str,
        property_id: str,
        ip_address: str,
        user_agent: str,
    ) -> dict[str, Any]:
        """Record a warning acknowledgement for a specific property.

        Runs inside a transaction: verify active record exists and outcome
        is ``ELIGIBLE_WITH_WARNING``, create the acknowledgement
        idempotently, and write a ``SUITABILITY_ACKNOWLEDGED`` audit log
        entry. If any step fails the transaction rolls back — no
        acknowledgement is persisted.
        """
    async def acknowledge(
        self,
        user_id: str,
        tenant_id: str,
        property_id: str,
        ip_address: str,
        user_agent: str,
    ) -> dict[str, Any]:
        """Record a warning acknowledgement for a specific property.

        Uses the session's existing transaction (started by get_db).
        Verifies active record exists and outcome is ELIGIBLE_WITH_WARNING,
        creates the acknowledgement idempotently, and writes a
        SUITABILITY_ACKNOWLEDGED audit log entry. Any exception causes the
        session to roll back automatically when get_db closes it.
        """
        # Load active suitability record.
        active_record = await self.suitability_repo.get_active(user_id, tenant_id)

        if (
            active_record is None
            or active_record.outcome != SuitabilityOutcome.ELIGIBLE_WITH_WARNING
        ):
            raise ValidationException(
                "Current outcome does not require acknowledgement"
            )

        # Verify the record hasn't expired.
        now = datetime.now(timezone.utc)
        if active_record.expires_at <= now:
            raise ValidationException(
                "Active suitability record is required"
            )

        # Build the acknowledgement instance.
        ack = SuitabilityAcknowledgement(
            id=str(uuid4()),
            tenant_id=tenant_id,
            suitability_id=active_record.id,
            user_id=user_id,
            property_id=property_id,
            acknowledged_at=now,
            ip_address=ip_address,
            user_agent=user_agent[:512] if user_agent else None,
            created_at=now,
        )

        # Idempotent create — returns existing row on conflict (Req 4.5).
        persisted_ack = await self.ack_repo.idempotent_create(ack)

        # Write SUITABILITY_ACKNOWLEDGED audit log entry.
        await self._write_audit_log(
            user_id=user_id,
            action=AuditAction.SUITABILITY_ACKNOWLEDGED,
            ip_address=ip_address,
            user_agent=user_agent[:512] if user_agent else None,
            tenant_id=tenant_id,
            metadata={
                "property_id": property_id,
                "suitability_id": active_record.id,
            },
        )

        await self.db.flush()

        return {
            "acknowledgement_id": persisted_ack.id,
            "suitability_id": persisted_ack.suitability_id,
            "user_id": persisted_ack.user_id,
            "property_id": persisted_ack.property_id,
            "acknowledged_at": persisted_ack.acknowledged_at,
            "tenant_id": persisted_ack.tenant_id,
        }

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _write_audit_log(
        self,
        user_id: str,
        action: AuditAction,
        ip_address: str | None,
        user_agent: str | None,
        tenant_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Insert a row into the audit_logs table within the current transaction.

        Mirrors the logging pattern used by ``kyc_service.py``. The insert
        participates in the caller's transaction boundary — if it fails,
        the whole transaction rolls back.
        """
        stmt = text(
            """
            INSERT INTO audit_logs (id, user_id, action, ip_address, user_agent, timestamp_utc, tenant_id, metadata)
            VALUES (:id, :user_id, :action, :ip_address, :user_agent, :timestamp_utc, :tenant_id, CAST(:metadata AS JSONB))
            """
        )
        await self.db.execute(
            stmt,
            {
                "id": str(uuid4()),
                "user_id": user_id,
                "action": action.value,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "timestamp_utc": datetime.now(timezone.utc),
                "tenant_id": tenant_id,
                "metadata": json.dumps(metadata) if metadata else None,
            },
        )
