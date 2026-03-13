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


def _parse_pct(value) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace("%", "").strip())
    except (TypeError, ValueError):
        return None


def _f(d: dict, *keys):
    """Safe nested dict access, returns None if any key is missing."""
    v = d
    for k in keys:
        if not isinstance(v, dict):
            return None
        v = v.get(k)
    return v


async def _fetch_and_store_prediction(fixture_id: int) -> bool:
    data = await api_client.get(
        "/predictions",
        params={"fixture": fixture_id},
        job_name=JOB_NAME,
    )
    response = data.get("response", [])
    if not response:
        return False

    entry = response[0]
    pred = entry.get("predictions") or {}
    winner = pred.get("winner") or {}
    percent = pred.get("percent") or {}
    goals_pred = pred.get("goals") or {}
    cmp = entry.get("comparison") or {}
    home_t = _f(entry, "teams", "home") or {}
    away_t = _f(entry, "teams", "away") or {}
    home_l5 = home_t.get("last_5") or {}
    away_l5 = away_t.get("last_5") or {}
    home_lg = home_t.get("league") or {}
    away_lg = away_t.get("league") or {}

    values = dict(
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
        goals_pred_home=goals_pred.get("home"),
        goals_pred_away=goals_pred.get("away"),
        # Comparison
        cmp_form_home=_parse_pct(_f(cmp, "form", "home")),
        cmp_form_away=_parse_pct(_f(cmp, "form", "away")),
        cmp_att_home=_parse_pct(_f(cmp, "att", "home")),
        cmp_att_away=_parse_pct(_f(cmp, "att", "away")),
        cmp_def_home=_parse_pct(_f(cmp, "def", "home")),
        cmp_def_away=_parse_pct(_f(cmp, "def", "away")),
        cmp_poisson_home=_parse_pct(_f(cmp, "poisson_distribution", "home")),
        cmp_poisson_away=_parse_pct(_f(cmp, "poisson_distribution", "away")),
        cmp_h2h_home=_parse_pct(_f(cmp, "h2h", "home")),
        cmp_h2h_away=_parse_pct(_f(cmp, "h2h", "away")),
        cmp_goals_home=_parse_pct(_f(cmp, "goals", "home")),
        cmp_goals_away=_parse_pct(_f(cmp, "goals", "away")),
        cmp_total_home=_parse_pct(_f(cmp, "total", "home")),
        cmp_total_away=_parse_pct(_f(cmp, "total", "away")),
        # Last 5
        home_last5_form=_parse_pct(home_l5.get("form")),
        home_last5_att=_parse_pct(home_l5.get("att")),
        home_last5_def=_parse_pct(home_l5.get("def")),
        home_last5_goals_for_avg=_f(home_l5, "goals", "for", "average"),
        home_last5_goals_against_avg=_f(home_l5, "goals", "against", "average"),
        away_last5_form=_parse_pct(away_l5.get("form")),
        away_last5_att=_parse_pct(away_l5.get("att")),
        away_last5_def=_parse_pct(away_l5.get("def")),
        away_last5_goals_for_avg=_f(away_l5, "goals", "for", "average"),
        away_last5_goals_against_avg=_f(away_l5, "goals", "against", "average"),
        # Season – home
        home_season_form=home_lg.get("form"),
        home_clean_sheet_home=_f(home_lg, "clean_sheet", "home"),
        home_clean_sheet_away=_f(home_lg, "clean_sheet", "away"),
        home_clean_sheet_total=_f(home_lg, "clean_sheet", "total"),
        home_failed_to_score_total=_f(home_lg, "failed_to_score", "total"),
        home_wins_home=_f(home_lg, "fixtures", "wins", "home"),
        home_wins_away=_f(home_lg, "fixtures", "wins", "away"),
        home_draws_total=_f(home_lg, "fixtures", "draws", "total"),
        home_loses_total=_f(home_lg, "fixtures", "loses", "total"),
        home_goals_for_avg_total=_f(home_lg, "goals", "for", "average", "total"),
        home_goals_against_avg_total=_f(home_lg, "goals", "against", "average", "total"),
        # Season – away
        away_season_form=away_lg.get("form"),
        away_clean_sheet_home=_f(away_lg, "clean_sheet", "home"),
        away_clean_sheet_away=_f(away_lg, "clean_sheet", "away"),
        away_clean_sheet_total=_f(away_lg, "clean_sheet", "total"),
        away_failed_to_score_total=_f(away_lg, "failed_to_score", "total"),
        away_wins_home=_f(away_lg, "fixtures", "wins", "home"),
        away_wins_away=_f(away_lg, "fixtures", "wins", "away"),
        away_draws_total=_f(away_lg, "fixtures", "draws", "total"),
        away_loses_total=_f(away_lg, "fixtures", "loses", "total"),
        away_goals_for_avg_total=_f(away_lg, "goals", "for", "average", "total"),
        away_goals_against_avg_total=_f(away_lg, "goals", "against", "average", "total"),
        raw_json=entry,
        fetched_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    stmt = pg_insert(FixturePrediction).values(**values).on_conflict_do_update(
        constraint="uq_fixture_predictions_fixture_id",
        set_={k: v for k, v in values.items() if k != "fixture_id"},
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
