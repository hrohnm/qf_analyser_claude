import asyncio
import logging
from datetime import date, datetime

from sqlalchemy import cast, Date, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.session import AsyncSessionLocal
from app.models.fixture import Fixture
from app.models.fixture_injury import FixtureInjury
from app.services.injury_impact_service import recompute_fixture_injury_impacts
from app.sync.budget_manager import budget_manager
from app.sync.client import api_client

logger = logging.getLogger(__name__)

JOB_NAME = "sync_injuries_today"
BATCH_SIZE = 20
CONCURRENCY = 2


def _chunks(items: list[int], size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]


async def _sync_batch_ids(ids: list[int]) -> int:
    ids_param = "-".join(str(i) for i in ids)
    data = await api_client.get(
        "/injuries",
        params={"ids": ids_param},
        job_name=JOB_NAME,
    )
    response = data.get("response", [])

    async with AsyncSessionLocal() as db:
        # Replace state for processed fixtures (works also when there are zero injuries)
        await db.execute(
            FixtureInjury.__table__.delete().where(FixtureInjury.fixture_id.in_(ids))
        )

        inserted = 0
        for row in response:
            fixture = row.get("fixture") or {}
            team = row.get("team") or {}
            player = row.get("player") or {}
            injury = row.get("injury") or {}

            stmt = pg_insert(FixtureInjury).values(
                fixture_id=fixture.get("id"),
                team_id=team.get("id"),
                player_id=player.get("id"),
                team_name=team.get("name"),
                player_name=player.get("name"),
                injury_type=injury.get("type"),
                injury_reason=injury.get("reason"),
                fetched_at=datetime.utcnow(),
            ).on_conflict_do_nothing(
                constraint="uq_fixture_injury_entry"
            )
            await db.execute(stmt)
            inserted += 1

        await db.commit()

    # Recompute injury impact per fixture after injuries are refreshed.
    async with AsyncSessionLocal() as db:
        for fixture_id in ids:
            await recompute_fixture_injury_impacts(db, fixture_id)

    return inserted


async def sync_injuries_for_today(season_year: int = 2025, force: bool = False) -> dict:
    today = date.today()
    async with AsyncSessionLocal() as db:
        fixture_ids = [
            row[0] for row in (
                await db.execute(
                    select(Fixture.id)
                    .where(
                        Fixture.season_year == season_year,
                        cast(Fixture.kickoff_utc, Date) == today,
                    )
                    .order_by(Fixture.kickoff_utc)
                )
            ).all()
        ]

    if not fixture_ids:
        return {"fixtures_today": 0, "fetched": 0, "skipped": 0, "errors": 0, "api_calls": 0}

    batches = list(_chunks(fixture_ids, BATCH_SIZE))

    # API sparing: one batch call can include up to 20 fixtures.
    # With today's fixture volume this is usually one request/day.
    semaphore = asyncio.Semaphore(CONCURRENCY)
    result = {
        "fixtures_today": len(fixture_ids),
        "fetched": 0,
        "skipped": 0,
        "errors": 0,
        "api_calls": 0,
    }

    async def process_batch(ids: list[int]):
        async with semaphore:
            async with AsyncSessionLocal() as db:
                if not await budget_manager.can_spend(db, calls=1):
                    logger.warning("Budget low, skipping injuries batch: %s", ids)
                    result["errors"] += 1
                    return
            try:
                inserted = await _sync_batch_ids(ids)
                result["fetched"] += inserted
                result["api_calls"] += 1
            except Exception as exc:
                logger.error("Injuries sync failed for ids=%s: %s", ids, exc)
                result["errors"] += 1

    await asyncio.gather(*[process_batch(ids) for ids in batches])
    return result
