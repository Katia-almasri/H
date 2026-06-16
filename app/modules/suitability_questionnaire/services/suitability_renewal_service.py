"""Suitability renewal service.

Handles three renewal-related concerns:

1. **on_kyc_approved** — idempotent insert of a suitability completion marker
   when an Investor's KYC is approved for the first time.
2. **on_material_kyc_change** — immediate invalidation of the active suitability
   record when a material KYC field (nationality or source_of_funds) changes.
3. **enqueue_renewal_notifications** — periodic worker that scans records
   approaching or past expiry and dispatches at-most-once-per-24h /
   at-most-four-per-record renewal notifications via Redis deduplication.

All methods operate within the caller's transaction boundary (no internal
begin/commit) unless stated otherwise.

Requirements: 1.1, 1.4, 6.1, 6.3, 6.4, 6.5, 7.1–7.6.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.enums.audit_action import AuditAction
from app.modules.suitability_questionnaire.models.audit_log_entry import (
    create_audit_log_entry,
)
from app.modules.suitability_questionnaire.repositories import (
    InvestorSuitabilityRepository,
    SuitabilityCompletionMarkerRepository,
)

if TYPE_CHECKING:
    from app.modules.suitability_questionnaire.models.investor_suitability import (
        InvestorSuitability,
    )

logger = logging.getLogger(__name__)

# Allowed material KYC field names that trigger invalidation.
_ALLOWED_FIELD_NAMES: frozenset[str] = frozenset({"nationality", "source_of_funds"})

# Renewal notification constraints.
_RENEWAL_WINDOW_DAYS: int = 30
_MAX_NOTIFICATIONS_PER_RECORD: int = 4
_DEDUP_TTL_SECONDS: int = 24 * 60 * 60  # 24 hours


class SuitabilityRenewalService:
    """Service managing suitability renewal, KYC-triggered invalidation, and notifications."""

    def __init__(self, db: AsyncSession, redis_client: Redis | None = None) -> None:
        self.db = db
        self.redis = redis_client
        self.suitability_repo = InvestorSuitabilityRepository(db)
        self.marker_repo = SuitabilityCompletionMarkerRepository(db)

    # ── KYC approval hook ─────────────────────────────────────────────────────

    async def on_kyc_approved(
        self,
        user_id: str,
        tenant_id: str,
        kyc_submission_id: str,
    ) -> None:
        """Idempotently mark an Investor as requiring suitability completion.

        Called from ``KYCService.approve_kyc`` inside the same transaction.
        Uses ``ON CONFLICT (user_id, tenant_id) DO NOTHING`` so repeated
        approvals are safe.
        """
        await self.marker_repo.mark(user_id, tenant_id, kyc_submission_id)

    # ── Material KYC change hook ──────────────────────────────────────────────

    async def on_material_kyc_change(
        self,
        user_id: str,
        tenant_id: str,
        field_name: str,
    ) -> None:
        """Invalidate the active suitability record on a material KYC change.

        Sets ``expires_at = now()`` on the active record and writes a
        ``SUITABILITY_INVALIDATED`` audit log entry. No-op when no active
        record exists.

        Caller-driven transaction — the invalidation and audit log commit
        or roll back atomically with the KYC change.

        Args:
            user_id: Investor's user id.
            tenant_id: Current tenant discriminator.
            field_name: One of ``"nationality"`` or ``"source_of_funds"``.

        Raises:
            ValueError: If ``field_name`` is not in the allowed set.
        """
        if field_name not in _ALLOWED_FIELD_NAMES:
            raise ValueError(
                f"Invalid field_name '{field_name}'. "
                f"Allowed values: {sorted(_ALLOWED_FIELD_NAMES)}"
            )

        record = await self.suitability_repo.get_active(user_id, tenant_id)
        if record is None:
            # No active suitability record — nothing to invalidate.
            return

        # Expire the active record immediately.
        await self.suitability_repo.mark_expired_now(record.id, tenant_id)

        # Write audit log entry in the same transaction.
        entry = create_audit_log_entry(
            user_id=user_id,
            tenant_id=tenant_id,
            action=AuditAction.SUITABILITY_INVALIDATED,
            metadata={"field_name": field_name},
        )
        self.db.add(entry)
        await self.db.flush()

    # ── Renewal notification worker ──────────────────────────────────────────

    async def enqueue_renewal_notifications(
        self,
        tenant_id: str,
    ) -> int:
        """Scan records due for renewal and dispatch notifications.

        Window: records where ``expires_at`` is within 30 days before now
        OR up to 30 days after now (i.e., ``now - 30d <= expires_at <= now + 30d``).

        Enforces:
        - At most once per 24 hours per investor (Redis key with 24h TTL).
        - At most four notifications total per suitability record (Redis counter).

        Returns the count of notifications dispatched in this run.
        """
        if self.redis is None:
            logger.warning(
                "Redis unavailable — skipping renewal notifications for tenant=%s",
                tenant_id,
            )
            return 0

        now = datetime.now(timezone.utc)
        window_start = now - timedelta(days=_RENEWAL_WINDOW_DAYS)
        window_end = now + timedelta(days=_RENEWAL_WINDOW_DAYS)

        dispatched = 0
        offset = 0
        batch_size = 100

        while True:
            records = await self.suitability_repo.scan_expiring(
                tenant_id=tenant_id,
                window_start=window_start,
                window_end=window_end,
                limit=batch_size,
                offset=offset,
            )
            if not records:
                break

            for record in records:
                sent = await self._try_send_notification(record)
                if sent:
                    dispatched += 1

            offset += batch_size

        return dispatched

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _try_send_notification(self, record: InvestorSuitability) -> bool:
        """Attempt to send a renewal notification for a single record.

        Returns True if the notification was dispatched, False if suppressed
        by the deduplication constraints.
        """
        assert self.redis is not None  # noqa: S101 — caller checks

        suitability_id = record.id
        count_key = f"sq:renewal:{suitability_id}:count"
        last_at_key = f"sq:renewal:{suitability_id}:last_at"

        try:
            # Check at-most-four-per-record constraint.
            count_raw = await self.redis.get(count_key)
            current_count = int(count_raw) if count_raw is not None else 0
            if current_count >= _MAX_NOTIFICATIONS_PER_RECORD:
                return False

            # Check at-most-once-per-24h constraint.
            last_at_raw = await self.redis.get(last_at_key)
            if last_at_raw is not None:
                # Key exists with a 24h TTL — notification was already sent recently.
                return False

            # Dispatch the notification.
            await self._send_renewal_notification(
                user_id=record.user_id,
                tenant_id=record.tenant_id,
                record=record,
            )

            # Update Redis state.
            await self.redis.set(
                last_at_key,
                datetime.now(timezone.utc).isoformat(),
                ex=_DEDUP_TTL_SECONDS,
            )
            await self.redis.incr(count_key)

            return True

        except Exception:
            logger.exception(
                "Failed to process renewal notification for suitability_id=%s",
                suitability_id,
            )
            return False

    async def _send_renewal_notification(
        self,
        user_id: str,
        tenant_id: str,
        record: InvestorSuitability,
    ) -> None:
        """Placeholder for renewal notification dispatch.

        The real notification module integration comes in a future sprint.
        For now, this logs the intended notification.
        """
        logger.info(
            "Renewal notification dispatched: user_id=%s tenant_id=%s "
            "suitability_id=%s expires_at=%s",
            user_id,
            tenant_id,
            record.id,
            record.expires_at,
        )
