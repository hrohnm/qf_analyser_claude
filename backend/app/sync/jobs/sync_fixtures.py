"""
Sync all fixtures for the current season across all 18 configured leagues.

Each league requires 1 API call → 18 calls total per full run.
Fixtures are upserted (INSERT ... ON CONFLICT DO UPDATE) so re-runs are safe.
"""
import asyncio
import re
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.league import League
from app.models.team import Team
from app.models.fixture import Fixture
from app.sync.client import api_client
from app.sync.leagues_config import LEAGUES

logger = logging.getLogger(__name__)

JOB_NAME = "sync_fixtures_current_season"


def _extract_matchday(round_str: str | None) -> int | None:
    """Extract numeric matchday from strings like 'Regular Season - 12'."""
    if not round_str:
        return None
    match = re.search(r"\d+", round_str)
    return int(match.group()) if match else None


async def _upsert_league(db: AsyncSession, league_cfg: dict, season_year: int) -> None:
    stmt = pg_insert(League).values(
        id=league_cfg["id"],
        name=league_cfg["name"],
        country=league_cfg["country"],
        tier=league_cfg["tier"],
        current_season=season_year,
        is_active=True,
        updated_at=datetime.utcnow(),
    ).on_conflict_do_update(
        index_elements=["id"],
        set_={
            "name": league_cfg["name"],
            "current_season": season_year,
            "updated_at": datetime.utcnow(),
        }
    )
    await db.execute(stmt)


async def _upsert_team(db: AsyncSession, team_data: dict) -> None:
    stmt = pg_insert(Team).values(
        id=team_data["id"],
        name=team_data["name"],
        logo_url=team_data.get("logo"),
        updated_at=datetime.utcnow(),
    ).on_conflict_do_update(
        index_elements=["id"],
        set_={
            "name": team_data["name"],
            "logo_url": team_data.get("logo"),
            "updated_at": datetime.utcnow(),
        }
    )
    await db.execute(stmt)


async def _upsert_fixture(db: AsyncSession, fix: dict, league_id: int, season_year: int) -> None:
    f = fix["fixture"]
    goals = fix.get("goals") or {}
    score = fix.get("score") or {}
    halftime = score.get("halftime") or {}

    stmt = pg_insert(Fixture).values(
        id=f["id"],
        league_id=league_id,
        season_year=season_year,
        home_team_id=fix["teams"]["home"]["id"],
        away_team_id=fix["teams"]["away"]["id"],
        kickoff_utc=(
            datetime.fromisoformat(f["date"].replace("Z", "+00:00")).replace(tzinfo=None)
            if f.get("date") else None
        ),
        round=fix["league"].get("round"),
        matchday=_extract_matchday(fix["league"].get("round")),
        status_short=f["status"]["short"],
        status_long=f["status"]["long"],
        elapsed=f["status"].get("elapsed"),
        home_score=goals.get("home"),
        away_score=goals.get("away"),
        home_ht_score=halftime.get("home"),
        away_ht_score=halftime.get("away"),
        referee=f.get("referee"),
        venue_name=f.get("venue", {}).get("name"),
        raw_json=fix,
        fetched_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    ).on_conflict_do_update(
        index_elements=["id"],
        set_={
            "status_short": f["status"]["short"],
            "status_long": f["status"]["long"],
            "elapsed": f["status"].get("elapsed"),
            "home_score": goals.get("home"),
            "away_score": goals.get("away"),
            "home_ht_score": halftime.get("home"),
            "away_ht_score": halftime.get("away"),
            "raw_json": fix,
            "updated_at": datetime.utcnow(),
        }
    )
    await db.execute(stmt)


async def sync_league_fixtures(league_cfg: dict, season_year: int) -> dict:
    """Fetch and store all fixtures for one league/season. Returns summary."""
    league_id = league_cfg["id"]
    logger.info(f"Syncing fixtures: {league_cfg['name']} {season_year}")

    data = await api_client.get(
        "/fixtures",
        params={"league": league_id, "season": season_year},
        job_name=JOB_NAME,
    )

    fixtures = data.get("response", [])
    if not fixtures:
        logger.warning(f"No fixtures returned for league {league_id} season {season_year}")
        return {"league_id": league_id, "count": 0}

    async with AsyncSessionLocal() as db:
        await _upsert_league(db, league_cfg, season_year)

        # Collect unique teams first
        teams_seen: set[int] = set()
        for fix in fixtures:
            for side in ("home", "away"):
                team = fix["teams"][side]
                if team["id"] not in teams_seen:
                    await _upsert_team(db, team)
                    teams_seen.add(team["id"])

        # Upsert all fixtures
        for fix in fixtures:
            await _upsert_fixture(db, fix, league_id, season_year)

        await db.commit()

    logger.info(f"  → {len(fixtures)} fixtures saved for {league_cfg['name']}")
    return {"league_id": league_id, "league_name": league_cfg["name"], "count": len(fixtures)}


async def sync_all_fixtures(season_year: int | None = None) -> list[dict]:
    """
    Sync current season fixtures for all 18 leagues in parallel.
    All 18 API calls are fired concurrently (asyncio.gather) to minimize wall-clock time.
    If season_year is None, the current calendar year is used.
    Returns a list of per-league result dicts.
    """
    if season_year is None:
        now = datetime.utcnow()
        season_year = now.year if now.month >= 7 else now.year - 1

    logger.info(f"Starting parallel fixture sync for season {season_year} ({len(LEAGUES)} leagues)")

    # Limit concurrent DB writes to avoid deadlocks on shared team rows
    db_semaphore = asyncio.Semaphore(6)

    async def safe_sync(league_cfg: dict) -> dict:
        async with db_semaphore:
            for attempt in range(1, 4):
                try:
                    return await sync_league_fixtures(league_cfg, season_year)
                except Exception as exc:
                    if attempt < 3 and "deadlock" in str(exc).lower():
                        logger.warning(f"Deadlock for {league_cfg['name']}, retry {attempt}/3...")
                        await asyncio.sleep(attempt * 2)
                        continue
                    logger.error(f"Failed to sync {league_cfg['name']}: {exc}")
                    return {
                        "league_id": league_cfg["id"],
                        "league_name": league_cfg["name"],
                        "error": str(exc),
                    }

    results = await asyncio.gather(*[safe_sync(league) for league in LEAGUES])

    total = sum(r.get("count", 0) for r in results)
    logger.info(f"Fixture sync complete: {total} fixtures across {len(LEAGUES)} leagues")
    return list(results)
