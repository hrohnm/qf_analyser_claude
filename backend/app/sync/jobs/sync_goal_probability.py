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
FINISHED = {"FT", "AET", "PEN"}
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


async def backfill_goal_probability_for_season(
    season_year: int = 2025,
    force: bool = False,
    concurrency: int = 20,
) -> dict:
    """
    Compute FixtureGoalProbability for all FINISHED fixtures in a season
    that are currently missing this data.

    This is safe to run at any time — the service reads only from Fixture
    (match results + Elo), so no API budget is consumed.
    """
    async with AsyncSessionLocal() as db:
        all_result = await db.execute(
            select(Fixture.id)
            .where(
                Fixture.season_year == season_year,
                Fixture.status_short.in_(FINISHED),
                Fixture.home_score.is_not(None),
            )
            .order_by(Fixture.kickoff_utc)
        )
        all_ids = [r[0] for r in all_result.all()]

    if not all_ids:
        return {"total": 0, "computed": 0, "skipped": 0, "errors": 0}

    if not force:
        async with AsyncSessionLocal() as db:
            existing_result = await db.execute(
                select(FixtureGoalProbability.fixture_id)
                .where(FixtureGoalProbability.fixture_id.in_(all_ids))
                .distinct()
            )
            existing_ids = {r[0] for r in existing_result.all()}
        to_process = [fid for fid in all_ids if fid not in existing_ids]
    else:
        to_process = all_ids

    skipped = len(all_ids) - len(to_process)
    if not to_process:
        return {"total": len(all_ids), "computed": 0, "skipped": skipped, "errors": 0}

    sem = asyncio.Semaphore(concurrency)
    counts = {"computed": 0, "errors": 0}

    async def _process(fid: int):
        async with sem:
            try:
                async with AsyncSessionLocal() as db:
                    await recompute_goal_probability_for_fixture(db, fid)
                counts["computed"] += 1
            except Exception as exc:
                logger.error("Goal prob backfill failed fixture=%s: %s", fid, exc)
                counts["errors"] += 1

    await asyncio.gather(*[_process(fid) for fid in to_process])
    logger.info(
        "Goal prob backfill done: %d computed, %d skipped, %d errors",
        counts["computed"], skipped, counts["errors"],
    )
    return {"total": len(all_ids), "computed": counts["computed"], "skipped": skipped, "errors": counts["errors"]}
