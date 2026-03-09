import asyncio
import logging
from datetime import date, datetime

from sqlalchemy import cast, Date, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.session import AsyncSessionLocal
from app.models.fixture import Fixture
from app.models.fixture_prediction import FixturePrediction
from app.sync.budget_manager import budget_manager
from app.sync.client import api_client

logger = logging.getLogger(__name__)

JOB_NAME = "sync_predictions_today"
CONCURRENCY = 12


def _parse_pct(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace("%", "").strip())
    except (TypeError, ValueError):
        return None


async def _fetch_and_store_prediction(fixture_id: int) -> bool:
    data = await api_client.get(
        "/predictions",
        params={"fixture": fixture_id},
        job_name=JOB_NAME,
    )
    response = data.get("response", [])
    if not response:
        return False

    pred = response[0].get("predictions", {})
    winner = pred.get("winner") or {}
    percent = pred.get("percent") or {}

    stmt = pg_insert(FixturePrediction).values(
        fixture_id=fixture_id,
        winner_team_id=winner.get("id"),
        winner_name=winner.get("name"),
        winner_comment=winner.get("comment"),
        win_or_draw=pred.get("win_or_draw"),
        under_over=pred.get("under_over"),
        advice=pred.get("advice"),
        percent_home=_parse_pct(percent.get("home")),
        percent_draw=_parse_pct(percent.get("draw")),
        percent_away=_parse_pct(percent.get("away")),
        raw_json=response[0],
        fetched_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    ).on_conflict_do_update(
        constraint="uq_fixture_predictions_fixture_id",
        set_={
            "winner_team_id": winner.get("id"),
            "winner_name": winner.get("name"),
            "winner_comment": winner.get("comment"),
            "win_or_draw": pred.get("win_or_draw"),
            "under_over": pred.get("under_over"),
            "advice": pred.get("advice"),
            "percent_home": _parse_pct(percent.get("home")),
            "percent_draw": _parse_pct(percent.get("draw")),
            "percent_away": _parse_pct(percent.get("away")),
            "raw_json": response[0],
            "fetched_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        },
    )

    async with AsyncSessionLocal() as db:
        await db.execute(stmt)
        await db.commit()

    return True


async def sync_predictions_for_today(
    season_year: int = 2025,
    force: bool = False,
) -> dict:
    """Sync predictions for all fixtures of today."""
    today = date.today()

    async with AsyncSessionLocal() as db:
        stmt = (
            select(Fixture.id)
            .where(
                Fixture.season_year == season_year,
                cast(Fixture.kickoff_utc, Date) == today,
            )
            .order_by(Fixture.kickoff_utc)
        )
        fixture_ids = [row[0] for row in (await db.execute(stmt)).all()]

        if not force and fixture_ids:
            existing_stmt = select(FixturePrediction.fixture_id).where(
                FixturePrediction.fixture_id.in_(fixture_ids)
            )
            existing_ids = {row[0] for row in (await db.execute(existing_stmt)).all()}
            to_process = [fid for fid in fixture_ids if fid not in existing_ids]
        else:
            to_process = fixture_ids

    if not fixture_ids:
        return {
            "fetched": 0,
            "skipped": 0,
            "errors": 0,
            "api_calls": 0,
            "fixtures_today": 0,
        }

    skipped = len(fixture_ids) - len(to_process)
    if not to_process:
        return {
            "fetched": 0,
            "skipped": skipped,
            "errors": 0,
            "api_calls": 0,
            "fixtures_today": len(fixture_ids),
        }

    semaphore = asyncio.Semaphore(CONCURRENCY)
    result = {
        "fetched": 0,
        "skipped": skipped,
        "errors": 0,
        "api_calls": 0,
        "fixtures_today": len(fixture_ids),
    }

    async def process_fixture(fid: int):
        async with semaphore:
            async with AsyncSessionLocal() as db:
                if not await budget_manager.can_spend(db, calls=1):
                    logger.warning("Budget low, skipping prediction for fixture %s", fid)
                    result["errors"] += 1
                    return
            try:
                ok = await _fetch_and_store_prediction(fid)
                result["api_calls"] += 1
                if ok:
                    result["fetched"] += 1
            except Exception as exc:
                logger.error("Prediction sync failed for fixture %s: %s", fid, exc)
                result["errors"] += 1

    await asyncio.gather(*[process_fixture(fid) for fid in to_process])
    return result
