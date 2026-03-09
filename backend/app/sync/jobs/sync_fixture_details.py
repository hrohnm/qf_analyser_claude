"""
Sync fixture statistics and events for finished fixtures of given leagues.

Optimization strategy:
- For each fixture: statistics + events are fetched CONCURRENTLY (asyncio.gather)
  → 1 fixture = 2 API calls running in parallel instead of sequential
- Up to CONCURRENCY fixtures processed simultaneously
- Fixtures already in DB are SKIPPED (idempotent re-runs cost 0 calls)
- Budget checked before each fixture pair

Total calls per fixture: 2 (statistics + events)
"""
import asyncio
import logging
from datetime import datetime

from sqlalchemy import select, func, cast, Date
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.fixture import Fixture
from app.models.fixture_statistics import FixtureStatistics
from app.models.fixture_events import FixtureEvent
from app.sync.client import api_client
from app.sync.budget_manager import budget_manager

logger = logging.getLogger(__name__)

JOB_NAME = "sync_fixture_details"
CONCURRENCY = 24  # pairs of stats+events; global client limiter caps at 280 req/min
FINISHED_STATUSES = {"FT", "AET", "PEN"}


# ── Helpers to parse api-football responses ──────────────────────────────────

def _parse_int(val) -> int | None:
    if val is None:
        return None
    try:
        return int(str(val).replace("%", "").strip())
    except (ValueError, TypeError):
        return None


def _parse_float(val) -> float | None:
    if val is None:
        return None
    try:
        return float(str(val).replace("%", "").strip())
    except (ValueError, TypeError):
        return None


def _stat(stats_list: list, stat_type: str):
    for s in stats_list:
        if s.get("type") == stat_type:
            return s.get("value")
    return None


# ── Statistics ────────────────────────────────────────────────────────────────

async def _fetch_and_store_statistics(fixture_id: int) -> bool:
    data = await api_client.get(
        "/fixtures/statistics",
        params={"fixture": fixture_id},
        job_name=JOB_NAME,
    )
    teams_data = data.get("response", [])
    if not teams_data:
        return False

    async with AsyncSessionLocal() as db:
        for team_entry in teams_data:
            team_id = team_entry["team"]["id"]
            sl = team_entry.get("statistics", [])

            possession_raw = _stat(sl, "Ball Possession")
            xg_raw = _stat(sl, "expected_goals")

            stmt = pg_insert(FixtureStatistics).values(
                fixture_id=fixture_id,
                team_id=team_id,
                shots_on_goal=_parse_int(_stat(sl, "Shots on Goal")),
                shots_off_goal=_parse_int(_stat(sl, "Shots off Goal")),
                shots_total=_parse_int(_stat(sl, "Total Shots")),
                shots_blocked=_parse_int(_stat(sl, "Blocked Shots")),
                shots_inside_box=_parse_int(_stat(sl, "Shots insidebox")),
                shots_outside_box=_parse_int(_stat(sl, "Shots outsidebox")),
                fouls=_parse_int(_stat(sl, "Fouls")),
                corner_kicks=_parse_int(_stat(sl, "Corner Kicks")),
                offsides=_parse_int(_stat(sl, "Offsides")),
                ball_possession=_parse_float(possession_raw),
                yellow_cards=_parse_int(_stat(sl, "Yellow Cards")),
                red_cards=_parse_int(_stat(sl, "Red Cards")),
                goalkeeper_saves=_parse_int(_stat(sl, "Goalkeeper Saves")),
                passes_total=_parse_int(_stat(sl, "Total passes")),
                passes_accurate=_parse_int(_stat(sl, "Passes accurate")),
                pass_accuracy=_parse_float(_stat(sl, "Passes %")),
                expected_goals=_parse_float(xg_raw),
                fetched_at=datetime.utcnow(),
            ).on_conflict_do_update(
                constraint="uq_fixture_stats_fixture_team",
                set_={"fetched_at": datetime.utcnow()},
            )
            await db.execute(stmt)
        await db.commit()
    return True


# ── Events ────────────────────────────────────────────────────────────────────

async def _fetch_and_store_events(fixture_id: int) -> int:
    data = await api_client.get(
        "/fixtures/events",
        params={"fixture": fixture_id},
        job_name=JOB_NAME,
    )
    events = data.get("response", [])

    async with AsyncSessionLocal() as db:
        # Delete old events for this fixture and re-insert (events don't have natural unique key)
        await db.execute(
            FixtureEvent.__table__.delete().where(FixtureEvent.fixture_id == fixture_id)
        )
        for ev in events:
            time = ev.get("time", {})
            player = ev.get("player") or {}
            assist = ev.get("assist") or {}
            team = ev.get("team") or {}
            db.add(FixtureEvent(
                fixture_id=fixture_id,
                team_id=team.get("id", 0),
                elapsed=time.get("elapsed"),
                elapsed_extra=time.get("extra"),
                event_type=ev.get("type"),
                detail=ev.get("detail"),
                comments=ev.get("comments"),
                player_id=player.get("id"),
                player_name=player.get("name"),
                assist_id=assist.get("id"),
                assist_name=assist.get("name"),
                fetched_at=datetime.utcnow(),
            ))
        await db.commit()
    return len(events)


async def _load_existing_detail_sets(
    db: AsyncSession,
    fixture_ids: list[int],
) -> tuple[set[int], set[int]]:
    """Return fixture-id sets that already have statistics/events persisted."""
    if not fixture_ids:
        return set(), set()

    stats_result = await db.execute(
        select(FixtureStatistics.fixture_id)
        .where(FixtureStatistics.fixture_id.in_(fixture_ids))
        .distinct()
    )
    events_result = await db.execute(
        select(FixtureEvent.fixture_id)
        .where(FixtureEvent.fixture_id.in_(fixture_ids))
        .distinct()
    )
    stats_ids = {row[0] for row in stats_result.all()}
    events_ids = {row[0] for row in events_result.all()}
    return stats_ids, events_ids


# ── Main sync entry point ─────────────────────────────────────────────────────

async def sync_details_for_leagues(
    league_ids: list[int],
    season_year: int = 2025,
    force: bool = False,
) -> dict:
    """
    Fetch statistics + events for all finished fixtures of the given leagues.

    Args:
        league_ids: list of league IDs to process
        season_year: season to sync (default 2025)
        force: if True, re-fetch even if already in DB

    Returns:
        Summary dict with counts per league
    """
    async with AsyncSessionLocal() as db:
        stmt = (
            select(Fixture.id, Fixture.league_id)
            .where(
                Fixture.league_id.in_(league_ids),
                Fixture.season_year == season_year,
                Fixture.status_short.in_(FINISHED_STATUSES),
            )
            .order_by(Fixture.league_id, Fixture.kickoff_utc)
        )
        result = await db.execute(stmt)
        all_fixtures = result.all()

    to_process: list[tuple[int, bool, bool]] = []
    skipped = 0

    if force:
        for fixture_id, _ in all_fixtures:
            to_process.append((fixture_id, True, True))
    else:
        fixture_ids = [fixture_id for fixture_id, _ in all_fixtures]
        async with AsyncSessionLocal() as db:
            stats_ids, events_ids = await _load_existing_detail_sets(db, fixture_ids)

        for fixture_id, _ in all_fixtures:
            need_stats = fixture_id not in stats_ids
            need_events = fixture_id not in events_ids
            if not need_stats and not need_events:
                skipped += 1
                continue
            to_process.append((fixture_id, need_stats, need_events))

    total = len(to_process)
    estimated_calls = sum(int(need_stats) + int(need_events) for _, need_stats, need_events in to_process)
    logger.info(
        f"Fixture details sync: {total} to fetch, {skipped} already in DB "
        f"(~{estimated_calls} API calls)"
    )

    if total == 0:
        return {"fetched": 0, "skipped": skipped, "errors": 0, "api_calls": 0}

    semaphore = asyncio.Semaphore(CONCURRENCY)
    results = {"fetched": 0, "skipped": skipped, "errors": 0, "api_calls": 0}

    async def process_fixture(fixture_id: int, need_stats: bool, need_events: bool) -> None:
        async with semaphore:
            calls_needed = int(need_stats) + int(need_events)
            if calls_needed == 0:
                return

            # Budget check: only for missing endpoints
            async with AsyncSessionLocal() as db:
                if not await budget_manager.can_spend(db, calls=calls_needed):
                    logger.warning(f"Budget low, skipping fixture {fixture_id}")
                    results["errors"] += 1
                    return

            try:
                tasks = []
                if need_stats:
                    tasks.append(_fetch_and_store_statistics(fixture_id))
                if need_events:
                    tasks.append(_fetch_and_store_events(fixture_id))

                # Fetch only missing endpoints; partial failures are contained.
                responses = await asyncio.gather(
                    *tasks,
                    return_exceptions=True,
                )
                failures = [res for res in responses if isinstance(res, Exception)]
                if failures:
                    err = failures[0]
                    logger.error(f"Partial error for fixture {fixture_id}: {err}")
                    results["errors"] += 1
                else:
                    results["fetched"] += 1
                    results["api_calls"] += calls_needed
            except Exception as exc:
                logger.error(f"Error syncing fixture {fixture_id}: {exc}")
                results["errors"] += 1

    await asyncio.gather(*[
        process_fixture(fixture_id, need_stats, need_events)
        for fixture_id, need_stats, need_events in to_process
    ])

    logger.info(
        f"Fixture details complete: {results['fetched']} fetched, "
        f"{results['errors']} errors, {results['api_calls']} API calls used"
    )
    return results


async def sync_details_for_today(season_year: int = 2025) -> dict:
    """Shortcut: sync details for all leagues that have games today."""
    from datetime import date
    from app.models.league import League
    from sqlalchemy import cast, Date

    async with AsyncSessionLocal() as db:
        today = date.today()
        stmt = (
            select(Fixture.league_id)
            .where(cast(Fixture.kickoff_utc, Date) == today)
            .distinct()
        )
        result = await db.execute(stmt)
        league_ids = [row[0] for row in result.all()]

    if not league_ids:
        return {"message": "Keine Spiele heute", "league_ids": []}

    logger.info(f"Syncing details for today's leagues: {league_ids}")
    summary = await sync_details_for_leagues(league_ids, season_year=season_year)
    summary["league_ids"] = league_ids
    return summary
