"""
Sync pre-match odds from Betano (bookmaker_id=32) for today's fixtures.
1 API call per fixture; bookmaker filter reduces response size.
"""
import asyncio
import logging
from datetime import date, datetime

from sqlalchemy import cast, Date, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.session import AsyncSessionLocal
from app.models.fixture import Fixture
from app.models.fixture_odds import FixtureOdds
from app.sync.budget_manager import budget_manager
from app.sync.client import api_client

logger = logging.getLogger(__name__)

JOB_NAME = "sync_odds_today"
CONCURRENCY = 6
DEFAULT_BOOKMAKER_ID = 32  # Betano

TARGET_BET_IDS: set[int] = {1, 5, 6, 12, 16, 17, 26, 105, 106, 218, 219, 231, 232}


async def _fetch_and_store_odds(fixture_id: int, bookmaker_id: int) -> int:
    data = await api_client.get(
        "/odds",
        params={"fixture": fixture_id, "bookmaker": bookmaker_id},
        job_name=JOB_NAME,
    )
    results = data.get("response", [])
    if not results:
        return 0

    stored = 0
    async with AsyncSessionLocal() as db:
        for entry in results:
            for bm in entry.get("bookmakers", []):
                bm_id: int = bm["id"]
                bm_name: str = bm["name"]
                for bet in bm.get("bets", []):
                    bet_id: int = bet["id"]
                    if bet_id not in TARGET_BET_IDS:
                        continue
                    values = bet.get("values", [])
                    if not values:
                        continue
                    stmt = pg_insert(FixtureOdds).values(
                        fixture_id=fixture_id,
                        bookmaker_id=bm_id,
                        bookmaker_name=bm_name,
                        bet_id=bet_id,
                        bet_name=bet["name"],
                        values=values,
                        fetched_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                    ).on_conflict_do_update(
                        constraint="uq_fixture_odds_fixture_bookmaker_bet",
                        set_={
                            "bet_name": bet["name"],
                            "values": values,
                            "updated_at": datetime.utcnow(),
                        },
                    )
                    await db.execute(stmt)
                    stored += 1
        await db.commit()
    return stored


async def sync_odds_for_today(
    season_year: int = 2025,
    bookmaker_id: int = DEFAULT_BOOKMAKER_ID,
    force: bool = False,
) -> dict:
    today = date.today()
    async with AsyncSessionLocal() as db:
        fixture_ids: list[int] = [
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
        return {"fixtures_today": 0, "fetched": 0, "skipped": 0, "errors": 0, "api_calls": 0, "bet_rows": 0}

    if not force:
        async with AsyncSessionLocal() as db:
            existing = {
                row[0] for row in (
                    await db.execute(
                        select(FixtureOdds.fixture_id)
                        .where(
                            FixtureOdds.fixture_id.in_(fixture_ids),
                            FixtureOdds.bookmaker_id == bookmaker_id,
                        )
                        .distinct()
                    )
                ).all()
            }
        to_fetch = [fid for fid in fixture_ids if fid not in existing]
        skipped = len(existing)
    else:
        to_fetch = fixture_ids
        skipped = 0

    result = {
        "fixtures_today": len(fixture_ids),
        "fetched": 0,
        "skipped": skipped,
        "errors": 0,
        "api_calls": 0,
        "bet_rows": 0,
    }

    semaphore = asyncio.Semaphore(CONCURRENCY)

    async def process(fixture_id: int):
        async with semaphore:
            async with AsyncSessionLocal() as db:
                if not await budget_manager.can_spend(db, calls=1):
                    logger.warning("Budget low, skipping odds for fixture %s", fixture_id)
                    result["errors"] += 1
                    return
            try:
                rows = await _fetch_and_store_odds(fixture_id, bookmaker_id)
                result["fetched"] += 1
                result["api_calls"] += 1
                result["bet_rows"] += rows
            except Exception as exc:
                logger.error("Odds sync failed for fixture %s: %s", fixture_id, exc)
                result["errors"] += 1

    await asyncio.gather(*[process(fid) for fid in to_fetch])
    return result
