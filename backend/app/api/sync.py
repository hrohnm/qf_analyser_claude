import logging
from datetime import datetime, timedelta, date

from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.league import League
from app.sync.budget_manager import budget_manager
from app.sync.leagues_config import CUP_COMPANIONS
from app.sync.jobs.sync_injuries import sync_injuries_for_today
from app.sync.jobs.sync_goal_probability import sync_goal_probability_for_today, backfill_goal_probability_for_season
from app.sync.jobs.sync_predictions import sync_predictions_for_today
from app.sync.jobs.sync_fixtures import (
    sync_all_fixtures,
    sync_league_fixtures,
    sync_fixtures_for_date,
    sync_started_today_fixtures,
)
from app.sync.jobs.sync_fixture_details import sync_details_for_today, sync_details_for_leagues, sync_details_for_date
from app.sync.jobs.sync_odds import sync_odds_for_today, DEFAULT_BOOKMAKER_ID
from app.sync.live_refresh_runtime import MIN_INTERVAL_SECONDS, live_refresh_controller
from app.services.team_elo_service import recompute_team_elo_for_league
from app.services.team_form_service import recompute_team_form_for_league
from app.services.goal_timing_service import compute_goal_timing_for_league
from app.services.home_advantage_service import compute_home_advantage_for_league
from app.services.h2h_service import compute_h2h_for_league
from app.services.scoreline_service import compute_scoreline_for_league
from app.services.match_result_probability_service import compute_match_result_for_league
from app.services.value_bet_service import compute_value_bets_for_league
from app.services.team_profile_service import compute_team_profiles_for_league
from app.services.evaluation_service import evaluate_for_date, evaluate_backfill
from app.services.top_scorer_service import compute_top_scorer_for_league

router = APIRouter(prefix="/sync", tags=["Sync"])
logger = logging.getLogger(__name__)

_sync_running = False


async def _get_active_leagues(db: AsyncSession) -> list[League]:
    result = await db.execute(
        select(League)
        .where(League.is_active.is_(True))
        .order_by(League.country, League.tier, League.name)
    )
    return list(result.scalars().all())


async def _get_active_league_ids(db: AsyncSession) -> list[int]:
    return [league.id for league in await _get_active_leagues(db)]


async def _get_league_cfg_map(db: AsyncSession, league_ids: list[int]) -> dict[int, dict]:
    if not league_ids:
        return {}

    result = await db.execute(select(League).where(League.id.in_(league_ids)))
    leagues = result.scalars().all()
    return {
        league.id: {
            "id": league.id,
            "name": league.name,
            "country": league.country,
            "tier": league.tier,
        }
        for league in leagues
    }


class BudgetResponse(BaseModel):
    used_today: int
    remaining: int
    limit: int
    date: str


class BudgetSeedRequest(BaseModel):
    used_today: int
    limit: int | None = None


class BudgetSeedResponse(BudgetResponse):
    message: str


class SyncResult(BaseModel):
    message: str
    season_year: int
    results: list[dict] | None = None


class FixtureHistorySeasonResult(BaseModel):
    season_year: int
    leagues_synced: int
    api_calls: int
    fixtures_saved: int
    errors: int


class FixtureHistoryResult(BaseModel):
    message: str
    seasons: list[FixtureHistorySeasonResult]
    league_ids: list[int]
    total_api_calls: int
    total_fixtures_saved: int


class LiveFixtureRefreshResult(BaseModel):
    message: str
    season_year: int
    leagues: int
    fixtures: int
    results: list[dict] = []


class LiveRefreshSettingsResult(BaseModel):
    enabled: bool
    interval_seconds: int
    interval_minutes: float
    min_interval_seconds: int


class LiveRefreshSettingsUpdate(BaseModel):
    enabled: bool | None = None
    interval_seconds: int | None = None


class DetailsResult(BaseModel):
    message: str
    fetched: int
    skipped: int
    errors: int
    api_calls: int
    league_ids: list[int] = []


class PatternComputeResult(BaseModel):
    message: str
    season_year: int
    league_results: list[dict] = []


class PredictionsResult(BaseModel):
    message: str
    season_year: int
    fixtures_today: int
    fetched: int
    skipped: int
    errors: int
    api_calls: int


class InjuriesResult(BaseModel):
    message: str
    season_year: int
    fixtures_today: int
    fetched: int
    skipped: int
    errors: int
    api_calls: int


class OddsResult(BaseModel):
    message: str
    season_year: int
    bookmaker_id: int
    fixtures_today: int
    fetched: int
    skipped: int
    errors: int
    api_calls: int
    bet_rows: int


class EloSyncRow(BaseModel):
    league_id: int
    season_year: int
    teams: int
    matches: int


class EloSyncResult(BaseModel):
    message: str
    season_year: int
    results: list[EloSyncRow]


class FormSyncRow(BaseModel):
    league_id: int
    season_year: int
    window_size: int
    rows: int


class FormSyncResult(BaseModel):
    message: str
    season_year: int
    window_size: int
    results: list[FormSyncRow]


class GoalProbabilityResult(BaseModel):
    message: str
    season_year: int
    fixtures_today: int
    fetched: int
    skipped: int
    errors: int


def _serialize_live_refresh_settings() -> LiveRefreshSettingsResult:
    state = live_refresh_controller.get_state()
    return LiveRefreshSettingsResult(
        enabled=state.enabled,
        interval_seconds=state.interval_seconds,
        interval_minutes=round(state.interval_seconds / 60, 2),
        min_interval_seconds=MIN_INTERVAL_SECONDS,
    )


@router.get("/budget", response_model=BudgetResponse)
async def get_budget(db: AsyncSession = Depends(get_db)):
    """Zeigt das heutige API-Call-Budget an."""
    used = await budget_manager.get_usage_today(db)
    remaining = await budget_manager.get_remaining(db)
    limit = await budget_manager.get_effective_limit(db)
    return BudgetResponse(
        used_today=used,
        remaining=remaining,
        limit=limit,
        date=datetime.utcnow().date().isoformat(),
    )


@router.post("/budget/seed", response_model=BudgetSeedResponse)
async def seed_budget_from_live(payload: BudgetSeedRequest, db: AsyncSession = Depends(get_db)):
    """
    Set today's budget baseline once from live provider status.
    After this, tracking continues locally without repeated /status calls.
    """
    if payload.used_today < 0:
        raise HTTPException(status_code=400, detail="used_today must be >= 0")
    if payload.limit is not None and payload.limit <= 0:
        raise HTTPException(status_code=400, detail="limit must be > 0")
    if payload.limit is not None and payload.used_today > payload.limit:
        raise HTTPException(status_code=400, detail="used_today cannot exceed limit")

    await budget_manager.seed_from_live_status(
        db=db,
        used_today=payload.used_today,
        limit_day=payload.limit,
        source="manual_seed_endpoint",
    )
    used = await budget_manager.get_usage_today(db)
    remaining = await budget_manager.get_remaining(db)
    limit = await budget_manager.get_effective_limit(db)
    return BudgetSeedResponse(
        message="Budget baseline from live status stored for today.",
        used_today=used,
        remaining=remaining,
        limit=limit,
        date=datetime.utcnow().date().isoformat(),
    )


@router.get("/live-refresh/settings", response_model=LiveRefreshSettingsResult)
async def get_live_refresh_settings():
    """Read the runtime settings for the automatic live refresh loop."""
    return _serialize_live_refresh_settings()


@router.patch("/live-refresh/settings", response_model=LiveRefreshSettingsResult)
async def update_live_refresh_settings(payload: LiveRefreshSettingsUpdate):
    """Pause/resume automatic live refresh and adjust its runtime interval."""
    if payload.enabled is None and payload.interval_seconds is None:
        raise HTTPException(status_code=400, detail="At least one setting must be provided.")
    if payload.interval_seconds is not None and payload.interval_seconds < MIN_INTERVAL_SECONDS:
        raise HTTPException(
            status_code=400,
            detail=f"interval_seconds must be >= {MIN_INTERVAL_SECONDS}",
        )

    live_refresh_controller.update(
        enabled=payload.enabled,
        interval_seconds=payload.interval_seconds,
    )
    return _serialize_live_refresh_settings()


@router.post("/fixtures", response_model=SyncResult)
async def trigger_fixture_sync(
    background_tasks: BackgroundTasks,
    season_year: int | None = None,
):
    """Startet den Fixture-Sync für alle 18 Ligen im Hintergrund."""
    global _sync_running
    if _sync_running:
        raise HTTPException(status_code=409, detail="Sync läuft bereits.")

    now = datetime.utcnow()
    effective_season = season_year or (now.year if now.month >= 7 else now.year - 1)

    async def run():
        global _sync_running
        _sync_running = True
        try:
            await sync_all_fixtures(effective_season)
        finally:
            _sync_running = False

    background_tasks.add_task(run)
    return SyncResult(
        message=f"Fixture-Sync für Saison {effective_season} gestartet (Hintergrund).",
        season_year=effective_season,
    )


@router.post("/fixtures/run", response_model=SyncResult)
async def trigger_fixture_sync_sync(season_year: int | None = None):
    """Startet den Fixture-Sync synchron und wartet auf das Ergebnis."""
    global _sync_running
    if _sync_running:
        raise HTTPException(status_code=409, detail="Sync läuft bereits.")

    now = datetime.utcnow()
    effective_season = season_year or (now.year if now.month >= 7 else now.year - 1)

    _sync_running = True
    try:
        results = await sync_all_fixtures(effective_season)
    finally:
        _sync_running = False

    return SyncResult(
        message="Fixture-Sync abgeschlossen.",
        season_year=effective_season,
        results=results,
    )


@router.post("/details/today", response_model=DetailsResult)
async def trigger_details_today(
    background_tasks: BackgroundTasks,
    season_year: int = 2025,
):
    """
    Startet Stats+Events-Sync für alle Ligen mit Spielen heute – im Hintergrund.
    Bereits vorhandene Daten werden übersprungen (idempotent).
    """
    global _sync_running
    if _sync_running:
        raise HTTPException(status_code=409, detail="Sync läuft bereits.")

    async def run():
        global _sync_running
        _sync_running = True
        try:
            await sync_details_for_today(season_year)
        finally:
            _sync_running = False

    background_tasks.add_task(run)
    return DetailsResult(
        message=f"Stats+Events-Sync gestartet (Hintergrund, Saison {season_year}).",
        fetched=0, skipped=0, errors=0, api_calls=0,
    )


@router.post("/details/run", response_model=DetailsResult)
async def trigger_details_run(
    season_year: int = 2025,
    league_ids: list[int] | None = None,
    force: bool = False,
):
    """
    Startet Stats+Events-Sync synchron und wartet auf das Ergebnis.
    league_ids: bestimmte Ligen; wenn leer → Ligen mit Spielen heute.
    force: auch bereits vorhandene Daten neu laden.
    """
    global _sync_running
    if _sync_running:
        raise HTTPException(status_code=409, detail="Sync läuft bereits.")

    _sync_running = True
    try:
        if league_ids:
            result = await sync_details_for_leagues(league_ids, season_year, force=force)
        else:
            result = await sync_details_for_today(season_year)
    finally:
        _sync_running = False

    return DetailsResult(
        message="Stats+Events-Sync abgeschlossen.",
        **{k: result.get(k, 0) for k in ["fetched", "skipped", "errors", "api_calls"]},
        league_ids=result.get("league_ids", league_ids or []),
    )


@router.post("/predictions/today", response_model=PredictionsResult)
async def trigger_predictions_today(
    background_tasks: BackgroundTasks,
    season_year: int = 2025,
    force: bool = False,
):
    """
    Sync predictions for all today's fixtures in background.
    Intended for daily morning run.
    """
    global _sync_running
    if _sync_running:
        raise HTTPException(status_code=409, detail="Sync läuft bereits.")

    async def run():
        global _sync_running
        _sync_running = True
        try:
            await sync_predictions_for_today(season_year=season_year, force=force)
        finally:
            _sync_running = False

    background_tasks.add_task(run)
    return PredictionsResult(
        message=f"Predictions-Sync für heute gestartet (Saison {season_year}).",
        season_year=season_year,
        fixtures_today=0,
        fetched=0,
        skipped=0,
        errors=0,
        api_calls=0,
    )


@router.post("/predictions/today/run", response_model=PredictionsResult)
async def trigger_predictions_today_run(
    season_year: int = 2025,
    force: bool = False,
):
    """Sync predictions for all today's fixtures and wait for result."""
    global _sync_running
    if _sync_running:
        raise HTTPException(status_code=409, detail="Sync läuft bereits.")

    _sync_running = True
    try:
        result = await sync_predictions_for_today(season_year=season_year, force=force)
    finally:
        _sync_running = False

    return PredictionsResult(
        message="Predictions-Sync für heute abgeschlossen.",
        season_year=season_year,
        fixtures_today=result.get("fixtures_today", 0),
        fetched=result.get("fetched", 0),
        skipped=result.get("skipped", 0),
        errors=result.get("errors", 0),
        api_calls=result.get("api_calls", 0),
    )


@router.post("/injuries/today", response_model=InjuriesResult)
async def trigger_injuries_today(
    background_tasks: BackgroundTasks,
    season_year: int = 2025,
):
    """Sync injuries for all today's fixtures in background."""
    global _sync_running
    if _sync_running:
        raise HTTPException(status_code=409, detail="Sync läuft bereits.")

    async def run():
        global _sync_running
        _sync_running = True
        try:
            await sync_injuries_for_today(season_year=season_year)
        finally:
            _sync_running = False

    background_tasks.add_task(run)
    return InjuriesResult(
        message=f"Injuries-Sync für heute gestartet (Saison {season_year}).",
        season_year=season_year,
        fixtures_today=0,
        fetched=0,
        skipped=0,
        errors=0,
        api_calls=0,
    )


@router.post("/injuries/today/run", response_model=InjuriesResult)
async def trigger_injuries_today_run(
    season_year: int = 2025,
):
    """Sync injuries for all today's fixtures and wait for result."""
    global _sync_running
    if _sync_running:
        raise HTTPException(status_code=409, detail="Sync läuft bereits.")

    _sync_running = True
    try:
        result = await sync_injuries_for_today(season_year=season_year)
    finally:
        _sync_running = False

    return InjuriesResult(
        message="Injuries-Sync für heute abgeschlossen.",
        season_year=season_year,
        fixtures_today=result.get("fixtures_today", 0),
        fetched=result.get("fetched", 0),
        skipped=result.get("skipped", 0),
        errors=result.get("errors", 0),
        api_calls=result.get("api_calls", 0),
    )


@router.post("/elo/run", response_model=EloSyncResult)
async def trigger_elo_recompute(
    season_year: int = 2025,
    league_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Recompute Team Elo snapshots for one league or all configured leagues."""
    league_ids = [league_id] if league_id is not None else await _get_active_league_ids(db)
    results: list[EloSyncRow] = []
    for lid in league_ids:
        row = await recompute_team_elo_for_league(
            db, league_id=lid, season_year=season_year,
            extra_league_ids=CUP_COMPANIONS.get(lid),
        )
        results.append(EloSyncRow(
            league_id=row["league_id"],
            season_year=row["season_year"],
            teams=row["teams"],
            matches=row["matches"],
        ))

    return EloSyncResult(
        message="Team Elo Recompute abgeschlossen.",
        season_year=season_year,
        results=results,
    )


@router.post("/form/run", response_model=FormSyncResult)
async def trigger_form_recompute(
    season_year: int = 2025,
    window_size: int = 5,
    league_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Recompute Team Form snapshots for one league or all configured leagues."""
    league_ids = [league_id] if league_id is not None else await _get_active_league_ids(db)
    results: list[FormSyncRow] = []
    for lid in league_ids:
        row = await recompute_team_form_for_league(
            db=db,
            league_id=lid,
            season_year=season_year,
            window_size=window_size,
            extra_league_ids=CUP_COMPANIONS.get(lid),
        )
        results.append(FormSyncRow(
            league_id=row["league_id"],
            season_year=row["season_year"],
            window_size=row["window_size"],
            rows=row["rows"],
        ))

    return FormSyncResult(
        message="Team Form Recompute abgeschlossen.",
        season_year=season_year,
        window_size=window_size,
        results=results,
    )


@router.post("/goal-probability/today/run", response_model=GoalProbabilityResult)
async def trigger_goal_probability_today_run(
    season_year: int = 2025,
    force: bool = False,
):
    """Compute weighted goal probabilities for today's upcoming fixtures."""
    global _sync_running
    if _sync_running:
        raise HTTPException(status_code=409, detail="Sync läuft bereits.")

    _sync_running = True
    try:
        result = await sync_goal_probability_for_today(season_year=season_year, force=force)
    finally:
        _sync_running = False

    return GoalProbabilityResult(
        message="Goal-Probability-Sync für heute abgeschlossen.",
        season_year=season_year,
        fixtures_today=result.get("fixtures_today", 0),
        fetched=result.get("fetched", 0),
        skipped=result.get("skipped", 0),
        errors=result.get("errors", 0),
    )


@router.post("/goal-probability/backfill")
async def goal_probability_backfill(
    season_year: int = 2025,
    force: bool = False,
):
    """
    Rückwirkend FixtureGoalProbability für alle abgeschlossenen Spiele der Saison berechnen.
    Kein API-Budget — reiner DB-Vorgang. Nötig für H/A⚽-Auswertung abgelaufener Spiele.
    """
    result = await backfill_goal_probability_for_season(season_year=season_year, force=force)
    return {
        "message": f"Goal-Probability Backfill Saison {season_year} abgeschlossen.",
        **result,
    }


@router.post("/fixtures/leagues/run", response_model=SyncResult)
async def trigger_fixture_sync_for_leagues(
    league_ids: list[int],
    season_year: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Fixture-Sync nur für bestimmte Ligen (synchron)."""
    global _sync_running
    if _sync_running:
        raise HTTPException(status_code=409, detail="Sync läuft bereits.")

    now = datetime.utcnow()
    effective_season = season_year or (now.year if now.month >= 7 else now.year - 1)

    league_map = await _get_league_cfg_map(db, league_ids)
    unknown = [lid for lid in league_ids if lid not in league_map]
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unbekannte Liga-IDs: {unknown}")

    _sync_running = True
    try:
        results = []
        for lid in league_ids:
            row = await sync_league_fixtures(league_map[lid], effective_season)
            results.append(row)
    finally:
        _sync_running = False

    return SyncResult(
        message=f"Fixture-Sync für Ligen {league_ids} abgeschlossen.",
        season_year=effective_season,
        results=results,
    )


@router.post("/fixtures/history/run", response_model=FixtureHistoryResult)
async def trigger_fixture_history_sync(
    seasons_back: int = 5,
    end_season_year: int | None = None,
    league_ids: list[int] | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Fixture-History-Sync für mehrere Saisons und aktive oder ausgewählte Ligen."""
    global _sync_running
    if _sync_running:
        raise HTTPException(status_code=409, detail="Sync läuft bereits.")
    if seasons_back < 1 or seasons_back > 10:
        raise HTTPException(status_code=400, detail="seasons_back must be between 1 and 10")

    now = datetime.utcnow()
    effective_end = end_season_year or (now.year if now.month >= 7 else now.year - 1)
    season_years = list(range(effective_end - seasons_back + 1, effective_end + 1))

    ids = league_ids or await _get_active_league_ids(db)
    if not ids:
        raise HTTPException(status_code=400, detail="Keine aktiven Ligen gefunden.")

    league_map = await _get_league_cfg_map(db, ids)
    unknown = [lid for lid in ids if lid not in league_map]
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unbekannte Liga-IDs: {unknown}")

    _sync_running = True
    try:
        season_results: list[FixtureHistorySeasonResult] = []
        total_api_calls = 0
        total_fixtures_saved = 0

        for season_year in season_years:
            results = []
            for lid in ids:
                row = await sync_league_fixtures(league_map[lid], season_year)
                results.append(row)

            fixtures_saved = sum(r.get("count", 0) for r in results)
            errors = sum(1 for r in results if r.get("error"))
            api_calls = len(results)
            season_results.append(
                FixtureHistorySeasonResult(
                    season_year=season_year,
                    leagues_synced=len(results),
                    api_calls=api_calls,
                    fixtures_saved=fixtures_saved,
                    errors=errors,
                )
            )
            total_api_calls += api_calls
            total_fixtures_saved += fixtures_saved
    finally:
        _sync_running = False

    return FixtureHistoryResult(
        message="Fixture-History-Sync abgeschlossen.",
        seasons=season_results,
        league_ids=ids,
        total_api_calls=total_api_calls,
        total_fixtures_saved=total_fixtures_saved,
    )


@router.post("/fixtures/live-today/run", response_model=LiveFixtureRefreshResult)
async def trigger_live_fixture_refresh_run(
    season_year: int = 2025,
):
    """Refresh today's fixtures whose kickoff time has already passed and which are not finished."""
    global _sync_running
    if _sync_running:
        raise HTTPException(status_code=409, detail="Sync läuft bereits.")

    _sync_running = True
    try:
        result = await sync_started_today_fixtures(season_year=season_year)
    finally:
        _sync_running = False

    return LiveFixtureRefreshResult(
        message="Live-Fixture-Refresh abgeschlossen.",
        season_year=season_year,
        leagues=result.get("leagues", 0),
        fixtures=result.get("fixtures", 0),
        results=result.get("results", []),
    )


@router.post("/odds/today/run", response_model=OddsResult)
async def trigger_odds_today_run(
    season_year: int = 2025,
    bookmaker_id: int = DEFAULT_BOOKMAKER_ID,
    force: bool = False,
):
    """Odds-Sync (Betano) für alle heutigen Fixtures – synchron."""
    global _sync_running
    if _sync_running:
        raise HTTPException(status_code=409, detail="Sync läuft bereits.")

    _sync_running = True
    try:
        result = await sync_odds_for_today(season_year=season_year, bookmaker_id=bookmaker_id, force=force)
    finally:
        _sync_running = False

    return OddsResult(
        message="Odds-Sync für heute abgeschlossen.",
        season_year=season_year,
        bookmaker_id=bookmaker_id,
        fixtures_today=result.get("fixtures_today", 0),
        fetched=result.get("fetched", 0),
        skipped=result.get("skipped", 0),
        errors=result.get("errors", 0),
        api_calls=result.get("api_calls", 0),
        bet_rows=result.get("bet_rows", 0),
    )


# ─── Pattern Compute Endpoints ───────────────────────────────────────────────

@router.post("/patterns/goal-timing/run", response_model=PatternComputeResult)
async def trigger_goal_timing(
    league_ids: list[int] | None = None,
    season_year: int = 2025,
    db: AsyncSession = Depends(get_db),
):
    """Berechnet Torzeit-Verteilung für alle Teams aus fixture_events (0 API Calls)."""
    ids = league_ids or await _get_active_league_ids(db)
    results = []
    for lid in ids:
        r = await compute_goal_timing_for_league(db, lid, season_year, extra_league_ids=CUP_COMPANIONS.get(lid))
        results.append({"league_id": lid, **r})
    return PatternComputeResult(
        message=f"GoalTiming für {len(ids)} Ligen berechnet.",
        season_year=season_year,
        league_results=results,
    )


@router.post("/patterns/home-advantage/run", response_model=PatternComputeResult)
async def trigger_home_advantage(
    league_ids: list[int] | None = None,
    season_year: int = 2025,
    db: AsyncSession = Depends(get_db),
):
    """Berechnet team-spezifischen Heimvorteil-Faktor (0 API Calls)."""
    ids = league_ids or await _get_active_league_ids(db)
    results = []
    for lid in ids:
        r = await compute_home_advantage_for_league(db, lid, season_year, extra_league_ids=CUP_COMPANIONS.get(lid))
        results.append({"league_id": lid, **r})
    return PatternComputeResult(
        message=f"HomeAdvantage für {len(ids)} Ligen berechnet.",
        season_year=season_year,
        league_results=results,
    )


@router.post("/patterns/h2h/run", response_model=PatternComputeResult)
async def trigger_h2h(
    league_ids: list[int] | None = None,
    season_year: int = 2025,
    db: AsyncSession = Depends(get_db),
):
    """Berechnet H2H-Stats für alle Fixtures aus bestehenden DB-Daten (0 API Calls)."""
    ids = league_ids or await _get_active_league_ids(db)
    results = []
    for lid in ids:
        r = await compute_h2h_for_league(db, lid, season_year)
        results.append({"league_id": lid, **r})
    return PatternComputeResult(
        message=f"H2H für {len(ids)} Ligen berechnet.",
        season_year=season_year,
        league_results=results,
    )


@router.post("/patterns/scoreline/run", response_model=PatternComputeResult)
async def trigger_scoreline(
    league_ids: list[int] | None = None,
    season_year: int = 2025,
    db: AsyncSession = Depends(get_db),
):
    """Berechnet Scoreline-Verteilung für alle Fixtures via Poisson (0 API Calls)."""
    ids = league_ids or await _get_active_league_ids(db)
    results = []
    for lid in ids:
        r = await compute_scoreline_for_league(db, lid, season_year)
        results.append({"league_id": lid, **r})
    return PatternComputeResult(
        message=f"Scoreline für {len(ids)} Ligen berechnet.",
        season_year=season_year,
        league_results=results,
    )


@router.post("/patterns/match-result/run", response_model=PatternComputeResult)
async def trigger_match_result(
    league_ids: list[int] | None = None,
    season_year: int = 2025,
    db: AsyncSession = Depends(get_db),
):
    """Berechnet finale 1X2+BTTS+O/U Wahrscheinlichkeiten kombiniert aus allen Sub-Pattern."""
    ids = league_ids or await _get_active_league_ids(db)
    results = []
    for lid in ids:
        r = await compute_match_result_for_league(db, lid, season_year)
        results.append({"league_id": lid, **r})
    return PatternComputeResult(
        message=f"MatchResultProbability für {len(ids)} Ligen berechnet.",
        season_year=season_year,
        league_results=results,
    )


@router.post("/patterns/value-bets/run", response_model=PatternComputeResult)
async def trigger_value_bets(
    league_ids: list[int] | None = None,
    season_year: int = 2025,
    db: AsyncSession = Depends(get_db),
):
    """Identifiziert Value Bets durch Vergleich Modell-Prob vs. Betano-Quoten."""
    ids = league_ids or await _get_active_league_ids(db)
    results = []
    for lid in ids:
        r = await compute_value_bets_for_league(db, lid, season_year)
        results.append({"league_id": lid, **r})
    return PatternComputeResult(
        message=f"ValueBets für {len(ids)} Ligen berechnet.",
        season_year=season_year,
        league_results=results,
    )


@router.post("/patterns/team-profiles/run", response_model=PatternComputeResult)
async def trigger_team_profiles(
    league_ids: list[int] | None = None,
    season_year: int = 2025,
    db: AsyncSession = Depends(get_db),
):
    """Berechnet Team-Saisonprofile (Angriff, Abwehr, Spielstil, Ratings) für alle Ligen."""
    ids = league_ids or await _get_active_league_ids(db)
    results = []
    for lid in ids:
        r = await compute_team_profiles_for_league(db, lid, season_year)
        results.append({"league_id": lid, **r})
    return PatternComputeResult(
        message=f"Team-Profile für {len(ids)} Ligen berechnet.",
        season_year=season_year,
        league_results=results,
    )


@router.post("/patterns/top-scorer/run", response_model=PatternComputeResult)
async def trigger_top_scorer(
    league_ids: list[int] | None = None,
    season_year: int = 2025,
    db: AsyncSession = Depends(get_db),
):
    """Berechnet Torschützen-Kandidaten aus Torhistorie, Team-Torpotenzial und Penalty-Signalen."""
    ids = league_ids or await _get_active_league_ids(db)
    results = []
    for lid in ids:
        r = await compute_top_scorer_for_league(db, lid, season_year)
        results.append({"league_id": lid, **r})
    return PatternComputeResult(
        message=f"Torschützen-Pattern für {len(ids)} Ligen berechnet.",
        season_year=season_year,
        league_results=results,
    )


@router.post("/patterns/all/run", response_model=PatternComputeResult)
async def trigger_all_patterns(
    league_ids: list[int] | None = None,
    season_year: int = 2025,
    db: AsyncSession = Depends(get_db),
):
    """Berechnet alle Pattern (GoalTiming + HomeAdv + H2H + Scoreline + MRP + ValueBets + TeamProfiles + TopScorer)."""
    ids = league_ids or await _get_active_league_ids(db)
    results = []
    for lid in ids:
        companions = CUP_COMPANIONS.get(lid)
        gt  = await compute_goal_timing_for_league(db, lid, season_year, extra_league_ids=companions)
        ha  = await compute_home_advantage_for_league(db, lid, season_year, extra_league_ids=companions)
        h2h = await compute_h2h_for_league(db, lid, season_year)
        sl  = await compute_scoreline_for_league(db, lid, season_year)
        mrp = await compute_match_result_for_league(db, lid, season_year)
        vb  = await compute_value_bets_for_league(db, lid, season_year)
        tp  = await compute_team_profiles_for_league(db, lid, season_year)
        ts  = await compute_top_scorer_for_league(db, lid, season_year)
        results.append({
            "league_id": lid,
            "goal_timing_teams": gt.get("teams", 0),
            "home_advantage_teams": ha.get("teams", 0),
            "h2h_fixtures": h2h.get("fixtures", 0),
            "scoreline_computed": sl.get("computed", 0),
            "mrp_computed": mrp.get("computed", 0),
            "value_bets_found": vb.get("total_bets", 0),
            "value_bets_fixtures": vb.get("fixtures_with_bets", 0),
            "team_profiles_computed": tp.get("computed", 0),
            "top_scorer_computed": ts.get("computed", 0),
        })
    return PatternComputeResult(
        message=f"Alle Pattern für {len(ids)} Ligen berechnet.",
        season_year=season_year,
        league_results=results,
    )


# ─── Pattern Evaluation ───────────────────────────────────────────────────────

@router.post("/evaluate/run")
async def trigger_evaluate(
    target_date: date | None = None,
    season_year: int = 2025,
):
    """
    Bewertet die Pattern-Genauigkeit für alle abgeschlossenen Spiele eines Datums.
    Standard: gestern. Metriken: 1X2-Treffer, Brier-Score, Over/Under, BTTS, Ergebnis.
    """
    d = target_date or (date.today() - timedelta(days=1))
    result = await evaluate_for_date(d, season_year)
    return {"message": f"Evaluation für {d} abgeschlossen.", "date": str(d), **result}


@router.post("/evaluate/backfill")
async def trigger_evaluate_backfill(
    season_year: int = 2025,
    force: bool = False,
):
    """
    Berechnet die Pattern-Evaluation rückwirkend für alle abgeschlossenen Fixtures
    mit MRP-Daten der angegebenen Saison.

    - force=false (Standard): überspringt bereits bewertete Fixtures
    - force=true: überschreibt alle bestehenden Evaluierungen
    """
    result = await evaluate_backfill(season_year=season_year, force=force)
    return {
        "message": f"Backfill abgeschlossen (Saison {season_year}, force={force}).",
        "season_year": season_year,
        **result,
    }


# ─── Morning Routine ──────────────────────────────────────────────────────────

class MorningRoutineResult(BaseModel):
    message: str
    season_year: int
    yesterday: date
    yesterday_fixtures_synced: int
    yesterday_details: dict
    yesterday_evaluation: dict
    predictions: dict
    injuries: dict
    odds: dict
    elo: list[dict]
    form: list[dict]
    goal_probability: dict
    patterns: list[dict]


@router.post("/morning-routine/run", response_model=MorningRoutineResult)
async def trigger_morning_routine(
    season_year: int = 2025,
    db: AsyncSession = Depends(get_db),
):
    """
    Tägliche Morgen-Routine – führt alle Sync- und Recompute-Schritte in der richtigen
    Reihenfolge aus:

    1. Gestrige Fixture-Ergebnisse aktualisieren (Scores, Status)
    2. Stats + Events für gestrige abgeschlossene Spiele laden
    3. Predictions für heutige Fixtures laden
    4. Injuries für heutige Fixtures laden
    5. Betano-Quoten für heutige Fixtures laden
    6. Elo + Form für alle Ligen recomputen (basieren auf finalen Ergebnissen)
    7. Goal-Probability für heutige Fixtures berechnen
    8. Alle Pattern recomputen (GoalTiming, HomeAdv, H2H, Scoreline, MRP, ValueBets, TopScorer)
    """
    global _sync_running
    if _sync_running:
        raise HTTPException(status_code=409, detail="Sync läuft bereits.")

    _sync_running = True
    yesterday = date.today() - timedelta(days=1)

    try:
        active_league_ids = await _get_active_league_ids(db)

        # ── 1. Gestrige Fixture-Ergebnisse aktualisieren ──────────────────────
        logger.info("[MorningRoutine] Step 1: Sync yesterday's fixture results")
        yesterday_league_results = await sync_fixtures_for_date(yesterday, season_year)
        yesterday_fixtures_synced = sum(r.get("count", 0) for r in yesterday_league_results)

        # ── 2. Stats + Events für gestrige Spiele ────────────────────────────
        logger.info("[MorningRoutine] Step 2: Sync stats+events for yesterday")
        yesterday_details = await sync_details_for_date(yesterday, season_year, force=False)

        # ── 2b. Pattern-Evaluation für gestrige Spiele ───────────────────────
        logger.info("[MorningRoutine] Step 2b: Evaluate pattern accuracy for yesterday")
        yesterday_evaluation = await evaluate_for_date(yesterday, season_year)

        # ── 3. Predictions für heute ─────────────────────────────────────────
        logger.info("[MorningRoutine] Step 3: Sync predictions for today")
        predictions_result = await sync_predictions_for_today(season_year=season_year, force=False)

        # ── 4. Injuries für heute ─────────────────────────────────────────────
        logger.info("[MorningRoutine] Step 4: Sync injuries for today")
        injuries_result = await sync_injuries_for_today(season_year=season_year)

        # ── 5. Betano-Quoten für heute ────────────────────────────────────────
        logger.info("[MorningRoutine] Step 5: Sync Betano odds for today")
        odds_result = await sync_odds_for_today(
            season_year=season_year,
            bookmaker_id=DEFAULT_BOOKMAKER_ID,
            force=False,
        )

        # ── 6. Elo + Form recomputen ──────────────────────────────────────────
        logger.info("[MorningRoutine] Step 6: Recompute Elo + Form for all leagues")
        elo_results = []
        form_results = []
        for lid in active_league_ids:
            companions = CUP_COMPANIONS.get(lid)
            elo_row = await recompute_team_elo_for_league(
                db, league_id=lid, season_year=season_year, extra_league_ids=companions,
            )
            elo_results.append(elo_row)
            form_row = await recompute_team_form_for_league(
                db, league_id=lid, season_year=season_year, extra_league_ids=companions,
            )
            form_results.append(form_row)

        # ── 7. Goal-Probability für heute ────────────────────────────────────
        logger.info("[MorningRoutine] Step 7: Compute goal probability for today")
        goal_prob_result = await sync_goal_probability_for_today(season_year=season_year, force=False)

        # ── 8. Alle Pattern recomputen ───────────────────────────────────────
        logger.info("[MorningRoutine] Step 8: Recompute all patterns for all leagues")
        pattern_results = []
        for lid in active_league_ids:
            companions = CUP_COMPANIONS.get(lid)
            gt  = await compute_goal_timing_for_league(db, lid, season_year, extra_league_ids=companions)
            ha  = await compute_home_advantage_for_league(db, lid, season_year, extra_league_ids=companions)
            h2h = await compute_h2h_for_league(db, lid, season_year)
            sl  = await compute_scoreline_for_league(db, lid, season_year)
            mrp = await compute_match_result_for_league(db, lid, season_year)
            vb  = await compute_value_bets_for_league(db, lid, season_year)
            ts  = await compute_top_scorer_for_league(db, lid, season_year)
            pattern_results.append({
                "league_id": lid,
                "goal_timing_teams": gt.get("teams", 0),
                "home_advantage_teams": ha.get("teams", 0),
                "h2h_fixtures": h2h.get("fixtures", 0),
                "scoreline_computed": sl.get("computed", 0),
                "mrp_computed": mrp.get("computed", 0),
                "value_bets_found": vb.get("total_bets", 0),
                "value_bets_fixtures": vb.get("fixtures_with_bets", 0),
                "top_scorer_computed": ts.get("computed", 0),
            })

        logger.info("[MorningRoutine] Complete.")
        return MorningRoutineResult(
            message="Morgen-Routine erfolgreich abgeschlossen.",
            season_year=season_year,
            yesterday=yesterday,
            yesterday_fixtures_synced=yesterday_fixtures_synced,
            yesterday_details=yesterday_details,
            yesterday_evaluation=yesterday_evaluation,
            predictions={
                "fixtures_today": predictions_result.get("fixtures_today", 0),
                "fetched": predictions_result.get("fetched", 0),
                "skipped": predictions_result.get("skipped", 0),
                "errors": predictions_result.get("errors", 0),
                "api_calls": predictions_result.get("api_calls", 0),
            },
            injuries={
                "fixtures_today": injuries_result.get("fixtures_today", 0),
                "fetched": injuries_result.get("fetched", 0),
                "errors": injuries_result.get("errors", 0),
                "api_calls": injuries_result.get("api_calls", 0),
            },
            odds={
                "fixtures_today": odds_result.get("fixtures_today", 0),
                "fetched": odds_result.get("fetched", 0),
                "skipped": odds_result.get("skipped", 0),
                "errors": odds_result.get("errors", 0),
                "api_calls": odds_result.get("api_calls", 0),
                "bet_rows": odds_result.get("bet_rows", 0),
                "bookmaker_id": DEFAULT_BOOKMAKER_ID,
            },
            elo=elo_results,
            form=form_results,
            goal_probability=goal_prob_result,
            patterns=pattern_results,
        )

    finally:
        _sync_running = False
