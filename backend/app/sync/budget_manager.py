from datetime import datetime, timezone
from sqlalchemy import and_, func, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.api_call_log import ApiCallLog


class BudgetExhaustedError(Exception):
    pass


class BudgetManager:
    SAFETY_RESERVE = 100
    BUDGET_SEED_JOB = "budget_seed"

    def __init__(self, daily_limit: int = settings.api_daily_limit):
        self.daily_limit = daily_limit

    @staticmethod
    def _utc_day_start() -> datetime:
        now_utc = datetime.now(timezone.utc)
        # DB stores naive datetimes in UTC; compare with naive UTC start.
        return datetime(now_utc.year, now_utc.month, now_utc.day)

    @staticmethod
    def _quota_relevant_filter():
        return (
            ApiCallLog.http_status.is_not(None),
            ApiCallLog.http_status != 429,
            ApiCallLog.job_name != BudgetManager.BUDGET_SEED_JOB,
            not_(
                and_(
                    ApiCallLog.http_status == 200,
                    ApiCallLog.error.is_not(None),
                    or_(
                        ApiCallLog.error.ilike("%rateLimit%"),
                        ApiCallLog.error.ilike("%too many requests%"),
                    ),
                )
            ),
        )

    async def _latest_budget_seed_today(self, db: AsyncSession) -> ApiCallLog | None:
        today_start = self._utc_day_start()
        result = await db.execute(
            select(ApiCallLog)
            .where(
                ApiCallLog.called_at >= today_start,
                ApiCallLog.job_name == self.BUDGET_SEED_JOB,
            )
            .order_by(ApiCallLog.called_at.desc(), ApiCallLog.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_usage_today(self, db: AsyncSession) -> int:
        today_start = self._utc_day_start()
        seed = await self._latest_budget_seed_today(db)

        if seed:
            base_used = int((seed.params_json or {}).get("provider_used", 0))
            local_result = await db.execute(
                select(func.count(ApiCallLog.id)).where(
                    ApiCallLog.called_at >= today_start,
                    ApiCallLog.id > seed.id,
                    *self._quota_relevant_filter(),
                )
            )
            return base_used + (local_result.scalar_one() or 0)

        result = await db.execute(
            select(func.count(ApiCallLog.id)).where(
                ApiCallLog.called_at >= today_start,
                *self._quota_relevant_filter(),
            )
        )
        return result.scalar_one() or 0

    async def get_effective_limit(self, db: AsyncSession) -> int:
        seed = await self._latest_budget_seed_today(db)
        if seed:
            raw = (seed.params_json or {}).get("provider_limit")
            if raw is not None:
                return int(raw)
        return self.daily_limit

    async def get_remaining(self, db: AsyncSession) -> int:
        used = await self.get_usage_today(db)
        effective_limit = await self.get_effective_limit(db)
        return max(0, effective_limit - used)

    async def seed_from_live_status(
        self,
        db: AsyncSession,
        used_today: int,
        limit_day: int | None = None,
        source: str = "manual",
    ) -> None:
        """
        Store one-time daily baseline from provider's live status.
        Following calls are tracked locally on top of this baseline.
        """
        params = {
            "provider_used": int(used_today),
            "provider_limit": int(limit_day) if limit_day is not None else None,
            "source": source,
        }
        log_entry = ApiCallLog(
            endpoint="/status",
            params_json=params,
            http_status=200,
            headers_limit=int(limit_day) if limit_day is not None else None,
            job_name=self.BUDGET_SEED_JOB,
            error=None,
        )
        db.add(log_entry)
        await db.commit()

    async def can_spend(self, db: AsyncSession, calls: int = 1) -> bool:
        remaining = await self.get_remaining(db)
        return remaining >= (calls + self.SAFETY_RESERVE)

    async def check_and_raise(self, db: AsyncSession, calls: int = 1, job_name: str = "") -> None:
        if not await self.can_spend(db, calls):
            remaining = await self.get_remaining(db)
            raise BudgetExhaustedError(
                f"API-Budget erschöpft: {remaining} verbleibend, "
                f"{calls + self.SAFETY_RESERVE} benötigt (inkl. Reserve {self.SAFETY_RESERVE}). "
                f"Job: {job_name}"
            )

    async def record_call(
        self,
        db: AsyncSession,
        endpoint: str,
        params: dict | None = None,
        http_status: int | None = None,
        headers: dict | None = None,
        job_name: str | None = None,
        error: str | None = None,
    ) -> None:
        remaining = None
        limit = None
        if headers:
            remaining = headers.get("x-ratelimit-requests-remaining")
            limit = headers.get("x-ratelimit-requests-limit")
            if remaining is not None:
                remaining = int(remaining)
            if limit is not None:
                limit = int(limit)

        log_entry = ApiCallLog(
            endpoint=endpoint,
            params_json=params,
            http_status=http_status,
            headers_remaining=remaining,
            headers_limit=limit,
            job_name=job_name,
            error=error,
        )
        db.add(log_entry)
        await db.commit()


budget_manager = BudgetManager()
