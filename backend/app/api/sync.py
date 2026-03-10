import logging
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.sync.budget_manager import budget_manager
from app.sync.leagues_config import LEAGUE_IDS
from app.sync.jobs.sync_injuries import sync_injuries_for_today
from app.sync.jobs.sync_goal_probability import sync_goal_probability_for_today
from app.sync.jobs.sync_predictions import sync_predictions_for_today
from app.sync.jobs.sync_fixtures import sync_all_fixtures
from app.sync.jobs.sync_fixture_details import sync_details_for_today, sync_details_for_leagues
from app.sync.jobs.sync_odds import sync_odds_for_today, DEFAULT_BOOKMAKER_ID
from app.services.team_elo_service import recompute_team_elo_for_league
from app.services.team_form_service import recompute_team_form_for_league

router = APIRouter(prefix="/sync", tags=["Sync"])
logger = logging.getLogger(__name__)

_sync_running = False


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


class DetailsResult(BaseModel):
    message: str
    fetched: int
    skipped: int
    errors: int
    api_calls: int
    league_ids: list[int] = []


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
    league_ids = [league_id] if league_id is not None else LEAGUE_IDS
    results: list[EloSyncRow] = []
    for lid in league_ids:
        row = await recompute_team_elo_for_league(db, league_id=lid, season_year=season_year)
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
    league_ids = [league_id] if league_id is not None else LEAGUE_IDS
    results: list[FormSyncRow] = []
    for lid in league_ids:
        row = await recompute_team_form_for_league(
            db=db,
            league_id=lid,
            season_year=season_year,
            window_size=window_size,
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


@router.post("/odds/today", response_model=OddsResult)
async def trigger_odds_today(
    background_tasks: BackgroundTasks,
    season_year: int = 2025,
    bookmaker_id: int = DEFAULT_BOOKMAKER_ID,
    force: bool = False,
):
    """Startet Odds-Sync für alle heutigen Fixtures im Hintergrund."""
    global _sync_running
    if _sync_running:
        raise HTTPException(status_code=409, detail="Sync läuft bereits.")

    async def run():
        global _sync_running
        _sync_running = True
        try:
            await sync_odds_for_today(season_year=season_year, bookmaker_id=bookmaker_id, force=force)
        finally:
            _sync_running = False

    background_tasks.add_task(run)
    return OddsResult(
        message=f"Odds-Sync für heute gestartet (Bookmaker {bookmaker_id}, Hintergrund).",
        season_year=season_year, bookmaker_id=bookmaker_id,
        fixtures_today=0, fetched=0, skipped=0, errors=0, api_calls=0, bet_rows=0,
    )


@router.post("/odds/today/run", response_model=OddsResult)
async def trigger_odds_today_run(
    season_year: int = 2025,
    bookmaker_id: int = DEFAULT_BOOKMAKER_ID,
    force: bool = False,
):
    """Startet Odds-Sync für alle heutigen Fixtures synchron und wartet auf Ergebnis."""
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
