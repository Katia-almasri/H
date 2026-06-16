"""Suitability investment gate service.

Provides the synchronous (in-process) decision function consumed by the
Investment module (Sprint 4) that translates the Investor's current
Active_Suitability_Record into one of:

- ``ALLOW``
- ``SUITABILITY_REQUIRED``
- ``SUITABILITY_BLOCKED``
- ``SUITABILITY_ACK_REQUIRED``

The gate reads at most twice (``get_active`` + ``get_acknowledgement``) and
never uses a cache — every evaluation hits the primary DB per the Sprint-1
financial-write rule.

On every blocking decision, a ``SUITABILITY_GATE_BLOCKED`` audit log entry
is written best-effort (failure is logged but does not affect the gate
response).

Requirements: 1.3, 4.2, 4.9, 5.1, 5.2, 6.2, 8.1–8.9, 9.3–9.5.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.enums.audit_action import AuditAction
from app.modules.suitability_questionnaire.enums import (
    GateDecisionKind,
    WarningReasonCode,
)
from app.modules.suitability_questionnaire.repositories import (
    InvestorSuitabilityRepository,
    SuitabilityAcknowledgementRepository,
)

if TYPE_CHECKING:
    from app.modules.suitability_questionnaire.models.investor_suitability import (
        InvestorSuitability,
    )

logger = logging.getLogger(__name__)


# ── GateDecision dataclass ────────────────────────────────────────────────────


@dataclass(frozen=True)
class GateDecision:
    """Immutable result returned by ``SuitabilityGateService.evaluate``.

    The ``kind`` field acts as a discriminator; other fields are populated
    depending on the decision type.
    """

    kind: GateDecisionKind
    suitability_id: str | None = None
    acknowledgement_id: str | None = None
    block_reason: str | None = None
    retake_allowed_at: datetime | None = None
    warning_reasons: tuple[WarningReasonCode, ...] = ()
    reason_indicator: str | None = None  # "NO_RECORD" | "EXPIRED" | "INVALID_SUBJECT"
    property_id: str | None = None


# ── Service ───────────────────────────────────────────────────────────────────


class SuitabilityGateService:
    """Evaluates whether an Investor may proceed with a property investment.

    Instantiated with an ``AsyncSession`` — no Redis or caching. The caller
    (future Investment module) creates the service via a dependency factory.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.suitability_repo = InvestorSuitabilityRepository(db)
        self.ack_repo = SuitabilityAcknowledgementRepository(db)

    async def evaluate(
        self,
        user_id: str,
        tenant_id: str,
        property_id: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> GateDecision:
        """Run the investment gate logic and return a structured decision.

        Steps:
        1. Fetch the active suitability record for ``(user_id, tenant_id)``.
        2. If missing → ``SUITABILITY_REQUIRED`` with reason ``NO_RECORD``.
        3. If expired → ``SUITABILITY_REQUIRED`` with reason ``EXPIRED``.
        4. If outcome is ``NOT_SUITABLE`` → ``SUITABILITY_BLOCKED``.
        5. If outcome is ``ELIGIBLE_WITH_WARNING``:
           - Check for acknowledgement → ``SUITABILITY_ACK_REQUIRED`` or ``ALLOW``.
        6. If outcome is ``ELIGIBLE`` → ``ALLOW``.
        """
        record = await self.suitability_repo.get_active(user_id, tenant_id)

        # ── No active record ──────────────────────────────────────────────
        if record is None:
            decision = GateDecision(
                kind=GateDecisionKind.SUITABILITY_REQUIRED,
                reason_indicator="NO_RECORD",
            )
            await self._audit_block(decision, user_id, tenant_id, property_id, ip_address, user_agent)
            return decision

        # ── Record expired ────────────────────────────────────────────────
        now = datetime.now(timezone.utc)
        if record.expires_at <= now:
            decision = GateDecision(
                kind=GateDecisionKind.SUITABILITY_REQUIRED,
                reason_indicator="EXPIRED",
                suitability_id=record.id,
            )
            await self._audit_block(decision, user_id, tenant_id, property_id, ip_address, user_agent)
            return decision

        # ── NOT_SUITABLE ──────────────────────────────────────────────────
        if record.outcome == "NOT_SUITABLE":
            decision = GateDecision(
                kind=GateDecisionKind.SUITABILITY_BLOCKED,
                block_reason=record.block_reason,
                retake_allowed_at=record.retake_allowed_at,
                suitability_id=record.id,
            )
            await self._audit_block(decision, user_id, tenant_id, property_id, ip_address, user_agent)
            return decision

        # ── ELIGIBLE_WITH_WARNING ─────────────────────────────────────────
        if record.outcome == "ELIGIBLE_WITH_WARNING":
            ack = await self.ack_repo.get(
                suitability_id=record.id,
                user_id=user_id,
                property_id=property_id,
                tenant_id=tenant_id,
            )
            if ack is None:
                decision = GateDecision(
                    kind=GateDecisionKind.SUITABILITY_ACK_REQUIRED,
                    warning_reasons=tuple(
                        WarningReasonCode(w) for w in record.warning_reasons
                    ),
                    property_id=property_id,
                    suitability_id=record.id,
                )
                await self._audit_block(decision, user_id, tenant_id, property_id, ip_address, user_agent)
                return decision

            # Acknowledgement present → allow
            return GateDecision(
                kind=GateDecisionKind.ALLOW,
                suitability_id=record.id,
                acknowledgement_id=ack.id,
            )

        # ── ELIGIBLE ──────────────────────────────────────────────────────
        return GateDecision(
            kind=GateDecisionKind.ALLOW,
            suitability_id=record.id,
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _audit_block(
        self,
        decision: GateDecision,
        user_id: str,
        tenant_id: str,
        property_id: str,
        ip_address: str | None,
        user_agent: str | None,
    ) -> None:
        """Best-effort audit log for blocking decisions.

        Wraps the insert in try/except so that an audit write failure never
        prevents the gate from returning its decision to the caller.

        Uses raw SQL insert into the ``audit_logs`` table to avoid coupling
        to a model that may not exist yet in every development environment.
        """
        try:
            import uuid
            from sqlalchemy import text

            now = datetime.now(timezone.utc)
            stmt = text(
                """
                INSERT INTO audit_logs (id, user_id, tenant_id, action, ip_address, user_agent, timestamp_utc, metadata)
                VALUES (:id, :user_id, :tenant_id, :action, :ip_address, :user_agent, :timestamp_utc, CAST(:metadata AS JSONB))
                """
            )
            import json

            await self.db.execute(
                stmt,
                {
                    "id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "tenant_id": tenant_id,
                    "action": AuditAction.SUITABILITY_GATE_BLOCKED.value,
                    "ip_address": ip_address,
                    "user_agent": (user_agent[:512] if user_agent else None),
                    "timestamp_utc": now,
                    "metadata": json.dumps({
                        "decision_kind": decision.kind.value,
                        "property_id": property_id,
                        "reason_indicator": decision.reason_indicator,
                        "suitability_id": decision.suitability_id,
                    }),
                },
            )
            await self.db.flush()
        except Exception:
            logger.exception(
                "Failed to write SUITABILITY_GATE_BLOCKED audit log for user=%s tenant=%s property=%s",
                user_id,
                tenant_id,
                property_id,
            )
