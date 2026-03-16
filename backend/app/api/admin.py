from datetime import datetime, date

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db, AsyncSessionLocal
from app.models.fixture import Fixture
from app.models.fixture_events import FixtureEvent
from app.models.fixture_statistics import FixtureStatistics
from app.models.league import League
from app.sync.client import api_client
from app.sync.jobs.sync_fixture_details import sync_details_for_leagues
from app.sync.jobs.sync_fixtures import sync_league_fixtures
from app.sync.jobs.sync_predictions import sync_predictions_for_today
from app.sync.jobs.sync_injuries import sync_injuries_for_today
from app.sync.jobs.sync_goal_probability import sync_goal_probability_for_today
from app.sync.leagues_config import LEAGUES, CUP_COMPANIONS
from app.services.team_elo_service import recompute_team_elo_for_league
from app.services.team_form_service import recompute_team_form_for_league
from app.services.goal_timing_service import compute_goal_timing_for_league
from app.services.home_advantage_service import compute_home_advantage_for_league
from app.services.h2h_service import compute_h2h_for_league
from app.services.scoreline_service import compute_scoreline_for_league
from app.services.match_result_probability_service import compute_match_result_for_league
from app.services.value_bet_service import compute_value_bets_for_league
from app.services.team_profile_service import compute_team_profiles_for_league
from app.services.top_scorer_service import compute_top_scorer_for_league

router = APIRouter(prefix="/admin", tags=["Administration"])

# Predefined leagues with their tier info
_PREDEFINED: dict[int, dict] = {l["id"]: l for l in LEAGUES}

# In-memory sync status per league_id
_sync_status: dict[int, dict] = {}

FINISHED_STATUSES = {"FT", "AET", "PEN"}

# Rough estimates for leagues not yet in DB (per tier)
_TYPICAL_FINISHED: dict[int, int] = {
    1: 280,   # Top flight: ~380 games, ~280 finished mid-season
    2: 400,   # Second division: ~552 games, ~400 finished
    3: 400,   # Third division: similar
    99: 350,  # Unknown
}


class LeagueAdminOut(BaseModel):
    id: int
    name: str
    country: str
    logo_url: str | None = None
    tier: int
    is_active: bool
    current_season: int | None = None

    model_config = {"from_attributes": True}


class LeagueToggleIn(BaseModel):
    is_active: bool


class SyncEstimateOut(BaseModel):
    league_id: int
    league_name: str
    fixtures_in_db: int
    finished_fixtures: int
    already_have_stats: int
    already_have_events: int
    # Calls needed:
    calls_fixtures: int        # Always 1 (reload fixtures list)
    calls_stats_needed: int    # finished without stats
    calls_events_needed: int   # finished without events
    estimated_total_calls: int
    is_estimate: bool          # True if no fixtures in DB yet (rough estimate)


# ── List / Toggle ─────────────────────────────────────────────────────────────

@router.get("/leagues", response_model=list[LeagueAdminOut])
async def list_all_leagues(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(League).order_by(League.country, League.tier, League.name)
    )
    return result.scalars().all()


@router.post("/leagues/fetch-from-api")
async def fetch_leagues_from_api(db: AsyncSession = Depends(get_db)):
    """Holt alle Ligen der Saison 2025 von API-Football und speichert sie in der DB."""
    data = await api_client.get(
        "/leagues",
        params={"season": 2025},
        job_name="admin_fetch_leagues",
    )

    leagues_data = data.get("response", [])
    imported = 0
    updated = 0
    auto_activated = 0

    for item in leagues_data:
        league_info = item.get("league", {})
        country_info = item.get("country", {})

        league_id = league_info.get("id")
        if not league_id:
            continue

        is_predefined = league_id in _PREDEFINED
        predefined = _PREDEFINED.get(league_id, {})
        existing = await db.get(League, league_id)

        if existing:
            if league_info.get("logo"):
                existing.logo_url = league_info["logo"]
            existing.current_season = 2025
            if is_predefined and not existing.is_active:
                existing.is_active = True
                auto_activated += 1
            updated += 1
        else:
            db.add(League(
                id=league_id,
                name=league_info.get("name", ""),
                country=country_info.get("name", ""),
                logo_url=league_info.get("logo"),
                tier=predefined.get("tier", 99),
                current_season=2025,
                is_active=is_predefined,
            ))
            imported += 1
            if is_predefined:
                auto_activated += 1

    await db.commit()
    return {
        "total_from_api": len(leagues_data),
        "imported": imported,
        "updated": updated,
        "auto_activated": auto_activated,
    }


@router.patch("/leagues/{league_id}")
async def toggle_league(
    league_id: int,
    body: LeagueToggleIn,
    db: AsyncSession = Depends(get_db),
):
    """Nur deaktivieren. Zum Aktivieren → activate-and-sync nutzen."""
    league = await db.get(League, league_id)
    if not league:
        raise HTTPException(status_code=404, detail="Liga nicht gefunden")
    league.is_active = body.is_active
    await db.commit()
    return {"id": league_id, "is_active": league.is_active}


# ── Sync Estimate ─────────────────────────────────────────────────────────────

@router.get("/leagues/{league_id}/sync-estimate", response_model=SyncEstimateOut)
async def sync_estimate(
    league_id: int,
    season_year: int = 2025,
    db: AsyncSession = Depends(get_db),
):
    """Schätzt die benötigten API-Calls zum vollständigen Laden einer Liga."""
    league = await db.get(League, league_id)
    if not league:
        raise HTTPException(status_code=404, detail="Liga nicht gefunden")

    # Count total fixtures in DB
    total_q = await db.execute(
        select(func.count()).where(
            Fixture.league_id == league_id,
            Fixture.season_year == season_year,
        )
    )
    fixtures_in_db: int = total_q.scalar_one()

    if fixtures_in_db == 0:
        # No fixtures in DB → rough estimate
        typical = _TYPICAL_FINISHED.get(league.tier, 350)
        return SyncEstimateOut(
            league_id=league_id,
            league_name=league.name,
            fixtures_in_db=0,
            finished_fixtures=typical,
            already_have_stats=0,
            already_have_events=0,
            calls_fixtures=1,
            calls_stats_needed=typical,
            calls_events_needed=typical,
            estimated_total_calls=1 + typical * 2,
            is_estimate=True,
        )

    # Count finished fixtures
    fin_q = await db.execute(
        select(func.count()).where(
            Fixture.league_id == league_id,
            Fixture.season_year == season_year,
            Fixture.status_short.in_(list(FINISHED_STATUSES)),
        )
    )
    finished: int = fin_q.scalar_one()

    # Count finished fixtures that already have stats
    stats_q = await db.execute(
        select(func.count(FixtureStatistics.fixture_id.distinct())).join(
            Fixture, Fixture.id == FixtureStatistics.fixture_id
        ).where(
            Fixture.league_id == league_id,
            Fixture.season_year == season_year,
        )
    )
    with_stats: int = stats_q.scalar_one()

    # Count finished fixtures that already have events
    events_q = await db.execute(
        select(func.count(FixtureEvent.fixture_id.distinct())).join(
            Fixture, Fixture.id == FixtureEvent.fixture_id
        ).where(
            Fixture.league_id == league_id,
            Fixture.season_year == season_year,
        )
    )
    with_events: int = events_q.scalar_one()

    need_stats = max(0, finished - with_stats)
    need_events = max(0, finished - with_events)

    return SyncEstimateOut(
        league_id=league_id,
        league_name=league.name,
        fixtures_in_db=fixtures_in_db,
        finished_fixtures=finished,
        already_have_stats=with_stats,
        already_have_events=with_events,
        calls_fixtures=1,
        calls_stats_needed=need_stats,
        calls_events_needed=need_events,
        estimated_total_calls=1 + need_stats + need_events,
        is_estimate=False,
    )


# ── Activate & Sync ───────────────────────────────────────────────────────────

@router.post("/leagues/{league_id}/activate-and-sync")
async def activate_and_sync(
    league_id: int,
    background_tasks: BackgroundTasks,
    season_year: int = 2025,
    db: AsyncSession = Depends(get_db),
):
    """
    Aktiviert eine Liga und startet den vollständigen Daten-Sync im Hintergrund:
    1. Fixtures laden
    2. Fixture-Details (Stats + Events) für alle abgeschlossenen Spiele
    """
    league = await db.get(League, league_id)
    if not league:
        raise HTTPException(status_code=404, detail="Liga nicht gefunden")

    if _sync_status.get(league_id, {}).get("status") == "running":
        raise HTTPException(status_code=409, detail="Sync für diese Liga läuft bereits.")

    # Activate immediately
    league.is_active = True
    await db.commit()

    league_cfg = {
        "id": league.id,
        "name": league.name,
        "country": league.country,
        "tier": league.tier,
    }
    league_name = league.name

    _sync_status[league_id] = {
        "status": "running",
        "phase": "fixtures",
        "started_at": datetime.utcnow().isoformat(),
        "league_name": league_name,
    }

    async def run_sync():
        try:
            companions = CUP_COMPANIONS.get(league_id)

            # Phase 1: Fixtures
            _sync_status[league_id]["phase"] = "fixtures"
            fixtures_result = await sync_league_fixtures(league_cfg, season_year)

            # Phase 2: Details (stats + events)
            _sync_status[league_id]["phase"] = "details"
            details_result = await sync_details_for_leagues(
                [league_id], season_year=season_year
            )

            # Phase 3: Pattern compute (Elo, Form, GoalTiming, HomeAdv, H2H, Scoreline, MRP, ValueBets, TopScorer)
            _sync_status[league_id]["phase"] = "patterns"
            async with AsyncSessionLocal() as db:
                await recompute_team_elo_for_league(db, league_id, season_year, extra_league_ids=companions)
                await recompute_team_form_for_league(db, league_id, season_year, extra_league_ids=companions)
                await compute_goal_timing_for_league(db, league_id, season_year, extra_league_ids=companions)
                await compute_home_advantage_for_league(db, league_id, season_year, extra_league_ids=companions)
                await compute_h2h_for_league(db, league_id, season_year)
                await compute_scoreline_for_league(db, league_id, season_year)
                await compute_match_result_for_league(db, league_id, season_year)
                await compute_value_bets_for_league(db, league_id, season_year)
                await compute_team_profiles_for_league(db, league_id, season_year)
                await compute_top_scorer_for_league(db, league_id, season_year)

            # Phase 4: If there are fixtures today → sync predictions, injuries, goal-probability
            _sync_status[league_id]["phase"] = "today_enrichment"
            today = date.today()
            async with AsyncSessionLocal() as db:
                today_count_q = await db.execute(
                    select(func.count()).where(
                        Fixture.league_id == league_id,
                        Fixture.season_year == season_year,
                        cast(Fixture.kickoff_utc, Date) == today,
                    )
                )
                fixtures_today: int = today_count_q.scalar_one()

            today_enrichment: dict = {"fixtures_today": fixtures_today}
            if fixtures_today > 0:
                pred = await sync_predictions_for_today(season_year=season_year, force=False)
                inj  = await sync_injuries_for_today(season_year=season_year)
                gp   = await sync_goal_probability_for_today(season_year=season_year, force=False)
                today_enrichment.update({
                    "predictions_fetched": pred.get("fetched", 0),
                    "injuries_fetched": inj.get("fetched", 0),
                    "goal_probability_computed": gp.get("fetched", 0),
                })

            _sync_status[league_id] = {
                "status": "done",
                "league_name": league_name,
                "fixtures_loaded": fixtures_result.get("count", 0),
                "details_fetched": details_result.get("fetched", 0),
                "details_skipped": details_result.get("skipped", 0),
                "api_calls_used": details_result.get("api_calls", 0) + 1,
                "errors": details_result.get("errors", 0),
                "today_enrichment": today_enrichment,
                "finished_at": datetime.utcnow().isoformat(),
            }
        except Exception as exc:
            _sync_status[league_id] = {
                "status": "error",
                "league_name": league_name,
                "error": str(exc),
                "finished_at": datetime.utcnow().isoformat(),
            }

    background_tasks.add_task(run_sync)

    return {
        "message": f"Liga '{league_name}' aktiviert. Sync läuft im Hintergrund.",
        "league_id": league_id,
        "season_year": season_year,
    }


@router.get("/leagues/{league_id}/sync-status")
async def get_sync_status(league_id: int):
    """Aktueller Status des Hintergrund-Syncs für eine Liga."""
    return _sync_status.get(league_id, {"status": "idle"})
