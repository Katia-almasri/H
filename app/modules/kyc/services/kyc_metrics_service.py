"""KYC metrics service."""

from datetime import date, datetime, time, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.kyc.enums import KYCMetricPeriod, KYCStatus
from app.modules.kyc.repositories import KYCSubmissionRepository
from app.modules.kyc.schemas.responses import KYCMetricsResponse

DAY_COUNT = 1
WEEK_DAYS = 7
FIRST_MONTH = 1
FIRST_DAY_OF_MONTH = 1
DECEMBER_MONTH = 12
SECONDS_PER_HOUR = 3600
PERCENTAGE_MULTIPLIER = 100
PERCENTAGE_DECIMAL_PLACES = 2


class KYCMetricsService:
    """Service for admin KYC metrics."""

    def __init__(self, db: AsyncSession):
        self.submission_repo = KYCSubmissionRepository(db)

    async def get_total_submissions(
        self,
        *,
        period_start: datetime,
        period_end: datetime,
    ) -> int:
        """Return total KYC submissions in the period."""
        return await self.submission_repo.count_submissions(
            submitted_from=period_start,
            submitted_to=period_end,
        )

    async def get_approved_submissions(
        self,
        *,
        period_start: datetime,
        period_end: datetime,
    ) -> int:
        """Return approved KYC submissions reviewed in the period."""
        return await self.submission_repo.count_submissions(
            status=KYCStatus.APPROVED.value,
            reviewed_from=period_start,
            reviewed_to=period_end,
        )

    async def get_rejected_submissions(
        self,
        *,
        period_start: datetime,
        period_end: datetime,
    ) -> int:
        """Return rejected KYC submissions reviewed in the period."""
        return await self.submission_repo.count_submissions(
            status=KYCStatus.REJECTED.value,
            reviewed_from=period_start,
            reviewed_to=period_end,
        )

    async def get_pending_kyc_count(self) -> int:
        """Return current KYC submissions awaiting admin decision."""
        pending = await self.submission_repo.count_submissions(
            status=KYCStatus.PENDING.value,
        )
        under_review = await self.submission_repo.count_submissions(
            status=KYCStatus.UNDER_REVIEW.value,
        )
        return pending + under_review

    async def get_average_review_time_seconds(
        self,
        *,
        period_start: datetime,
        period_end: datetime,
    ) -> float | None:
        """Return average review duration in seconds for reviewed submissions."""
        rows = await self.submission_repo.list_review_timestamps(
            reviewed_from=period_start,
            reviewed_to=period_end,
        )
        durations = [
            (reviewed_at - submitted_at).total_seconds()
            for submitted_at, reviewed_at in rows
            if reviewed_at >= submitted_at
        ]
        if not durations:
            return None
        return sum(durations) / len(durations)

    def get_approval_rate(
        self,
        *,
        approved_submissions: int,
        reviewed_submissions: int,
    ) -> float:
        """Return approval rate as a percentage of reviewed submissions."""
        return self._percentage(approved_submissions, reviewed_submissions)

    def get_rejection_rate(
        self,
        *,
        rejected_submissions: int,
        reviewed_submissions: int,
    ) -> float:
        """Return rejection rate as a percentage of reviewed submissions."""
        return self._percentage(rejected_submissions, reviewed_submissions)

    async def get_metrics(
        self,
        *,
        period: KYCMetricPeriod,
        reference_date: date,
    ) -> KYCMetricsResponse:
        """Return all KYC metrics for one period window."""
        period_start, period_end = self._resolve_period_window(period, reference_date)

        total_submissions = await self.get_total_submissions(
            period_start=period_start,
            period_end=period_end,
        )
        approved_submissions = await self.get_approved_submissions(
            period_start=period_start,
            period_end=period_end,
        )
        rejected_submissions = await self.get_rejected_submissions(
            period_start=period_start,
            period_end=period_end,
        )
        reviewed_submissions = approved_submissions + rejected_submissions
        pending_kyc_count = await self.get_pending_kyc_count()
        average_review_time_seconds = await self.get_average_review_time_seconds(
            period_start=period_start,
            period_end=period_end,
        )

        return KYCMetricsResponse(
            period=period,
            period_start=period_start,
            period_end=period_end,
            reference_date=reference_date,
            total_submissions=total_submissions,
            approved_submissions=approved_submissions,
            rejected_submissions=rejected_submissions,
            reviewed_submissions=reviewed_submissions,
            approval_rate=self.get_approval_rate(
                approved_submissions=approved_submissions,
                reviewed_submissions=reviewed_submissions,
            ),
            rejection_rate=self.get_rejection_rate(
                rejected_submissions=rejected_submissions,
                reviewed_submissions=reviewed_submissions,
            ),
            average_review_time_seconds=average_review_time_seconds,
            average_review_time_hours=(
                average_review_time_seconds / SECONDS_PER_HOUR
                if average_review_time_seconds is not None
                else None
            ),
            pending_kyc_count=pending_kyc_count,
        )

    def _resolve_period_window(
        self,
        period: KYCMetricPeriod,
        reference_date: date,
    ) -> tuple[datetime, datetime]:
        period_start = datetime.combine(reference_date, time.min)

        if period == KYCMetricPeriod.DAY:
            return period_start, period_start + timedelta(days=DAY_COUNT)

        if period == KYCMetricPeriod.WEEK:
            week_start = period_start - timedelta(days=reference_date.weekday())
            return week_start, week_start + timedelta(days=WEEK_DAYS)

        if period == KYCMetricPeriod.MONTH:
            month_start = period_start.replace(day=FIRST_DAY_OF_MONTH)
            next_month = (
                month_start.replace(
                    year=month_start.year + DAY_COUNT,
                    month=FIRST_MONTH,
                )
                if month_start.month == DECEMBER_MONTH
                else month_start.replace(month=month_start.month + DAY_COUNT)
            )
            return month_start, next_month

        year_start = period_start.replace(
            month=FIRST_MONTH,
            day=FIRST_DAY_OF_MONTH,
        )
        return year_start, year_start.replace(year=year_start.year + DAY_COUNT)

    def _percentage(self, numerator: int, denominator: int) -> float:
        if denominator == 0:
            return 0.0
        return round(
            (numerator / denominator) * PERCENTAGE_MULTIPLIER,
            PERCENTAGE_DECIMAL_PLACES,
        )
