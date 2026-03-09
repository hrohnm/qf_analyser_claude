import asyncio
import logging
from datetime import date

from sqlalchemy import cast, Date, select

from app.db.session import AsyncSessionLocal
from app.models.fixture import Fixture
from app.models.fixture_goal_probability import FixtureGoalProbability
from app.services.goal_probability_service import recompute_goal_probability_for_fixture

logger = logging.getLogger(__name__)

ACTIVE_OR_UPCOMING = {"NS", "TBD", "PST", "1H", "HT", "2H"}
CONCURRENCY = 10


async def sync_goal_probability_for_today(season_year: int = 2025, force: bool = False) -> dict:
    today = date.today()
    async with AsyncSessionLocal() as db:
        fixtures_result = await db.execute(
            select(Fixture.id)
            .where(
                Fixture.season_year == season_year,
                cast(Fixture.kickoff_utc, Date) == today,
                Fixture.status_short.in_(ACTIVE_OR_UPCOMING),
            )
            .order_by(Fixture.kickoff_utc)
        )
        fixture_ids = [row[0] for row in fixtures_result.all()]

        if not force and fixture_ids:
            existing = await db.execute(
                select(FixtureGoalProbability.fixture_id)
                .where(FixtureGoalProbability.fixture_id.in_(fixture_ids))
                .distinct()
            )
            existing_ids = {r[0] for r in existing.all()}
            to_process = [fid for fid in fixture_ids if fid not in existing_ids]
        else:
            to_process = fixture_ids

    if not fixture_ids:
        return {"fixtures_today": 0, "fetched": 0, "skipped": 0, "errors": 0}

    skipped = len(fixture_ids) - len(to_process)
    if not to_process:
        return {"fixtures_today": len(fixture_ids), "fetched": 0, "skipped": skipped, "errors": 0}

    semaphore = asyncio.Semaphore(CONCURRENCY)
    result = {"fixtures_today": len(fixture_ids), "fetched": 0, "skipped": skipped, "errors": 0}

    async def process(fid: int):
        async with semaphore:
            try:
                async with AsyncSessionLocal() as db:
                    await recompute_goal_probability_for_fixture(db, fid)
                result["fetched"] += 1
            except Exception as exc:
                logger.error("Goal probability sync failed for fixture %s: %s", fid, exc)
                result["errors"] += 1

    await asyncio.gather(*[process(fid) for fid in to_process])
    return result
