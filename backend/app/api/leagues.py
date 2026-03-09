from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.league import League
from app.models.team import Team
from app.models.team_elo_snapshot import TeamEloSnapshot
from app.models.team_form_snapshot import TeamFormSnapshot
from app.services.team_elo_service import recompute_team_elo_for_league
from app.services.team_form_service import recompute_team_form_for_league
from app.sync.leagues_config import LEAGUES

router = APIRouter(prefix="/leagues", tags=["Ligen"])


class LeagueOut(BaseModel):
    id: int
    name: str
    country: str
    tier: int
    current_season: int | None = None
    logo_url: str | None = None

    model_config = {"from_attributes": True}


class LeagueEloRowOut(BaseModel):
    rank: int
    team_id: int
    team_name: str
    team_logo_url: str | None = None
    elo_overall: float
    elo_home: float
    elo_away: float
    games_played: int
    elo_delta_last_5: float
    strength_tier: str
    computed_at: str | None = None
    model_version: str


class LeagueFormRowOut(BaseModel):
    rank: int
    team_id: int
    team_name: str
    team_logo_url: str | None = None
    scope: str
    form_score: float
    result_score: float
    performance_score: float
    trend_score: float
    opponent_strength_score: float
    elo_adjusted_result_score: float
    form_trend: str
    form_bucket: str
    games_considered: int
    computed_at: str | None = None
    model_version: str


@router.get("/", response_model=list[LeagueOut])
async def list_leagues(db: AsyncSession = Depends(get_db)):
    """Gibt alle in der DB gespeicherten Ligen zurück."""
    result = await db.execute(select(League).order_by(League.country, League.tier))
    return result.scalars().all()


@router.get("/config")
async def list_configured_leagues():
    """Gibt die Konfiguration aller 18 Ziel-Ligen zurück (auch ohne DB-Einträge)."""
    return LEAGUES


@router.get("/{league_id}/elo", response_model=list[LeagueEloRowOut])
async def league_elo(
    league_id: int,
    season_year: int,
    db: AsyncSession = Depends(get_db),
):
    """Elo-Powerranking einer Liga für eine Saison."""
    rows = await db.execute(
        select(TeamEloSnapshot, Team)
        .join(Team, Team.id == TeamEloSnapshot.team_id)
        .where(
            TeamEloSnapshot.league_id == league_id,
            TeamEloSnapshot.season_year == season_year,
        )
        .order_by(TeamEloSnapshot.elo_overall.desc())
    )
    data = rows.all()

    if not data:
        await recompute_team_elo_for_league(db, league_id=league_id, season_year=season_year)
        rows = await db.execute(
            select(TeamEloSnapshot, Team)
            .join(Team, Team.id == TeamEloSnapshot.team_id)
            .where(
                TeamEloSnapshot.league_id == league_id,
                TeamEloSnapshot.season_year == season_year,
            )
            .order_by(TeamEloSnapshot.elo_overall.desc())
        )
        data = rows.all()

    out: list[LeagueEloRowOut] = []
    for idx, (snap, team) in enumerate(data, start=1):
        out.append(LeagueEloRowOut(
            rank=idx,
            team_id=team.id,
            team_name=team.name,
            team_logo_url=team.logo_url,
            elo_overall=float(snap.elo_overall),
            elo_home=float(snap.elo_home),
            elo_away=float(snap.elo_away),
            games_played=snap.games_played,
            elo_delta_last_5=float(snap.elo_delta_last_5),
            strength_tier=snap.strength_tier,
            computed_at=snap.computed_at.isoformat() if snap.computed_at else None,
            model_version=snap.model_version,
        ))
    return out


@router.get("/{league_id}/form-table", response_model=list[LeagueFormRowOut])
async def league_form_table(
    league_id: int,
    season_year: int,
    window_size: int = 5,
    scope: str = "overall",
    db: AsyncSession = Depends(get_db),
):
    if scope not in {"overall", "home", "away"}:
        return []

    rows = await db.execute(
        select(TeamFormSnapshot, Team)
        .join(Team, Team.id == TeamFormSnapshot.team_id)
        .where(
            TeamFormSnapshot.league_id == league_id,
            TeamFormSnapshot.season_year == season_year,
            TeamFormSnapshot.window_size == window_size,
            TeamFormSnapshot.scope == scope,
        )
        .order_by(TeamFormSnapshot.form_score.desc())
    )
    data = rows.all()

    if not data:
        await recompute_team_form_for_league(
            db=db,
            league_id=league_id,
            season_year=season_year,
            window_size=window_size,
        )
        rows = await db.execute(
            select(TeamFormSnapshot, Team)
            .join(Team, Team.id == TeamFormSnapshot.team_id)
            .where(
                TeamFormSnapshot.league_id == league_id,
                TeamFormSnapshot.season_year == season_year,
                TeamFormSnapshot.window_size == window_size,
                TeamFormSnapshot.scope == scope,
            )
            .order_by(TeamFormSnapshot.form_score.desc())
        )
        data = rows.all()

    out: list[LeagueFormRowOut] = []
    for idx, (snap, team) in enumerate(data, start=1):
        out.append(LeagueFormRowOut(
            rank=idx,
            team_id=team.id,
            team_name=team.name,
            team_logo_url=team.logo_url,
            scope=snap.scope,
            form_score=float(snap.form_score),
            result_score=float(snap.result_score),
            performance_score=float(snap.performance_score),
            trend_score=float(snap.trend_score),
            opponent_strength_score=float(snap.opponent_strength_score),
            elo_adjusted_result_score=float(snap.elo_adjusted_result_score),
            form_trend=snap.form_trend,
            form_bucket=snap.form_bucket,
            games_considered=snap.games_considered,
            computed_at=snap.computed_at.isoformat() if snap.computed_at else None,
            model_version=snap.model_version,
        ))
    return out
