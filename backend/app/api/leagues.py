from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.league import League
from app.models.team import Team
from app.models.team_elo_snapshot import TeamEloSnapshot
from app.models.team_form_snapshot import TeamFormSnapshot
from app.models.team_season_profile import TeamSeasonProfile
from app.services.team_elo_service import recompute_team_elo_for_league
from app.services.team_form_service import recompute_team_form_for_league
from app.services.team_profile_service import compute_team_profiles_for_league
from app.sync.leagues_config import LEAGUES

router = APIRouter(prefix="/leagues", tags=["Ligen"])


class LeagueOut(BaseModel):
    id: int
    name: str
    country: str
    tier: int
    current_season: int | None = None
    logo_url: str | None = None
    is_active: bool = True

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


class TeamProfileRowOut(BaseModel):
    rank: int
    team_id: int
    team_name: str
    team_logo_url: str | None = None
    games_played: int
    # Attack
    goals_scored_pg: float
    xg_for_pg: float | None = None
    shots_total_pg: float | None = None
    shots_on_target_pg: float | None = None
    shots_on_target_ratio: float | None = None
    shot_conversion_rate: float | None = None
    shots_inside_box_pg: float | None = None
    # Defense
    goals_conceded_pg: float
    clean_sheet_rate: float
    xg_against_pg: float | None = None
    shots_against_pg: float | None = None
    shots_on_target_against_pg: float | None = None
    gk_saves_pg: float | None = None
    # Style
    possession_avg: float | None = None
    passes_pg: float | None = None
    pass_accuracy_avg: float | None = None
    corners_pg: float | None = None
    fouls_pg: float | None = None
    yellow_cards_pg: float | None = None
    red_cards_pg: float | None = None
    offsides_pg: float | None = None
    # xG performance
    xg_over_performance: float | None = None
    xg_defense_performance: float | None = None
    # Ratings
    attack_rating: float | None = None
    defense_rating: float | None = None
    intensity_rating: float | None = None
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


@router.get("/{league_id}/team-profiles", response_model=list[TeamProfileRowOut])
async def league_team_profiles(
    league_id: int,
    season_year: int,
    sort_by: str = "attack_rating",
    db: AsyncSession = Depends(get_db),
):
    """
    Team season profiles for a league — attack, defense, style metrics and
    0-100 composite ratings normalised within the league.

    sort_by: attack_rating | defense_rating | intensity_rating | goals_scored_pg |
             goals_conceded_pg | xg_over_performance
    """
    SORT_FIELDS = {
        "attack_rating": TeamSeasonProfile.attack_rating,
        "defense_rating": TeamSeasonProfile.defense_rating,
        "intensity_rating": TeamSeasonProfile.intensity_rating,
        "goals_scored_pg": TeamSeasonProfile.goals_scored_pg,
        "goals_conceded_pg": TeamSeasonProfile.goals_conceded_pg,
        "xg_over_performance": TeamSeasonProfile.xg_over_performance,
    }
    order_col = SORT_FIELDS.get(sort_by, TeamSeasonProfile.attack_rating)
    # For goals_conceded ascending (lower = better) invert
    order_expr = order_col.asc() if sort_by == "goals_conceded_pg" else order_col.desc()

    rows = await db.execute(
        select(TeamSeasonProfile, Team)
        .join(Team, Team.id == TeamSeasonProfile.team_id)
        .where(
            TeamSeasonProfile.league_id == league_id,
            TeamSeasonProfile.season_year == season_year,
        )
        .order_by(order_expr)
    )
    data = rows.all()

    if not data:
        await compute_team_profiles_for_league(db, league_id, season_year)
        rows = await db.execute(
            select(TeamSeasonProfile, Team)
            .join(Team, Team.id == TeamSeasonProfile.team_id)
            .where(
                TeamSeasonProfile.league_id == league_id,
                TeamSeasonProfile.season_year == season_year,
            )
            .order_by(order_expr)
        )
        data = rows.all()

    def _f(v) -> float | None:
        return float(v) if v is not None else None

    out: list[TeamProfileRowOut] = []
    for idx, (profile, team) in enumerate(data, start=1):
        out.append(TeamProfileRowOut(
            rank=idx,
            team_id=team.id,
            team_name=team.name,
            team_logo_url=team.logo_url,
            games_played=profile.games_played,
            goals_scored_pg=float(profile.goals_scored_pg),
            xg_for_pg=_f(profile.xg_for_pg),
            shots_total_pg=_f(profile.shots_total_pg),
            shots_on_target_pg=_f(profile.shots_on_target_pg),
            shots_on_target_ratio=_f(profile.shots_on_target_ratio),
            shot_conversion_rate=_f(profile.shot_conversion_rate),
            shots_inside_box_pg=_f(profile.shots_inside_box_pg),
            goals_conceded_pg=float(profile.goals_conceded_pg),
            clean_sheet_rate=float(profile.clean_sheet_rate),
            xg_against_pg=_f(profile.xg_against_pg),
            shots_against_pg=_f(profile.shots_against_pg),
            shots_on_target_against_pg=_f(profile.shots_on_target_against_pg),
            gk_saves_pg=_f(profile.gk_saves_pg),
            possession_avg=_f(profile.possession_avg),
            passes_pg=_f(profile.passes_pg),
            pass_accuracy_avg=_f(profile.pass_accuracy_avg),
            corners_pg=_f(profile.corners_pg),
            fouls_pg=_f(profile.fouls_pg),
            yellow_cards_pg=_f(profile.yellow_cards_pg),
            red_cards_pg=_f(profile.red_cards_pg),
            offsides_pg=_f(profile.offsides_pg),
            xg_over_performance=_f(profile.xg_over_performance),
            xg_defense_performance=_f(profile.xg_defense_performance),
            attack_rating=_f(profile.attack_rating),
            defense_rating=_f(profile.defense_rating),
            intensity_rating=_f(profile.intensity_rating),
            computed_at=profile.computed_at.isoformat() if profile.computed_at else None,
            model_version=profile.model_version,
        ))
    return out
