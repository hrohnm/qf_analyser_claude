from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.fixture import Fixture
from app.models.fixture_events import FixtureEvent
from app.models.fixture_statistics import FixtureStatistics
from app.models.team import Team
from app.models.team_elo_snapshot import TeamEloSnapshot
from app.models.team_form_snapshot import TeamFormSnapshot
from app.services.team_elo_service import recompute_team_elo_for_league
from app.services.team_form_service import recompute_team_form_for_league

router = APIRouter(prefix="/teams", tags=["Teams"])

FINISHED_STATUSES = {"FT", "AET", "PEN"}


class TeamLastMatchOut(BaseModel):
    fixture_id: int
    kickoff_utc: str | None = None
    league_id: int
    opponent_team_id: int
    opponent_team_name: str
    is_home: bool
    goals_for: int | None = None
    goals_against: int | None = None
    result: str | None = None  # W/D/L


class TeamSummaryOut(BaseModel):
    team_id: int
    team_name: str
    team_logo_url: str | None = None
    season_year: int
    league_id: int | None = None

    played: int
    won: int
    drawn: int
    lost: int
    points: int
    goals_for: int
    goals_against: int
    goal_diff: int
    goals_for_home: int
    goals_against_home: int
    goals_for_away: int
    goals_against_away: int
    form: str

    home_played: int
    home_points: int
    away_played: int
    away_points: int

    avg_goals_for: float
    avg_goals_against: float

    xg_total: float | None = None
    xg_total_home: float | None = None
    xg_total_away: float | None = None
    avg_ball_possession: float | None = None
    avg_ball_possession_home: float | None = None
    avg_ball_possession_away: float | None = None
    shots_total: int
    shots_total_home: int
    shots_total_away: int
    shots_on_goal: int
    shots_on_goal_home: int
    shots_on_goal_away: int
    corners: int
    corners_home: int
    corners_away: int
    fouls: int
    fouls_home: int
    fouls_away: int
    yellow_cards: int
    yellow_cards_home: int
    yellow_cards_away: int
    red_cards: int
    red_cards_home: int
    red_cards_away: int
    passes_total: int
    passes_total_home: int
    passes_total_away: int
    passes_accurate: int
    passes_accurate_home: int
    passes_accurate_away: int
    pass_accuracy_pct: float | None = None

    events_goals: int
    events_goals_home: int
    events_goals_away: int
    events_yellow_cards: int
    events_yellow_cards_home: int
    events_yellow_cards_away: int
    events_red_cards: int
    events_red_cards_home: int
    events_red_cards_away: int
    events_substitutions: int
    events_substitutions_home: int
    events_substitutions_away: int

    last_matches: list[TeamLastMatchOut]


class TeamEloOut(BaseModel):
    team_id: int
    team_name: str
    team_logo_url: str | None = None
    league_id: int
    season_year: int
    elo_overall: float
    elo_home: float
    elo_away: float
    games_played: int
    games_home: int
    games_away: int
    elo_delta_last_5: float
    strength_tier: str
    computed_at: str | None = None
    model_version: str


class TeamFormScopeOut(BaseModel):
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


class TeamFormOut(BaseModel):
    team_id: int
    team_name: str
    team_logo_url: str | None = None
    league_id: int
    season_year: int
    window_size: int
    scopes: list[TeamFormScopeOut]


def _points_for_result(result: str) -> int:
    if result == "W":
        return 3
    if result == "D":
        return 1
    return 0


@router.get("/{team_id}/summary", response_model=TeamSummaryOut)
async def team_summary(
    team_id: int,
    season_year: int = Query(..., description="Saison-Jahr, z.B. 2025"),
    league_id: int | None = Query(None, description="Optional auf Liga filtern"),
    db: AsyncSession = Depends(get_db),
):
    team = await db.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    stmt = (
        select(Fixture)
        .options(selectinload(Fixture.home_team), selectinload(Fixture.away_team))
        .where(
            Fixture.season_year == season_year,
            Fixture.status_short.in_(FINISHED_STATUSES),
            (Fixture.home_team_id == team_id) | (Fixture.away_team_id == team_id),
        )
        .order_by(Fixture.kickoff_utc)
    )
    if league_id is not None:
        stmt = stmt.where(Fixture.league_id == league_id)

    result = await db.execute(stmt)
    fixtures = result.scalars().all()

    if not fixtures:
        return TeamSummaryOut(
            team_id=team.id,
            team_name=team.name,
            team_logo_url=team.logo_url,
            season_year=season_year,
            league_id=league_id,
            played=0,
            won=0,
            drawn=0,
            lost=0,
            points=0,
            goals_for=0,
            goals_against=0,
            goal_diff=0,
            goals_for_home=0,
            goals_against_home=0,
            goals_for_away=0,
            goals_against_away=0,
            form="",
            home_played=0,
            home_points=0,
            away_played=0,
            away_points=0,
            avg_goals_for=0.0,
            avg_goals_against=0.0,
            xg_total=None,
            xg_total_home=None,
            xg_total_away=None,
            avg_ball_possession=None,
            avg_ball_possession_home=None,
            avg_ball_possession_away=None,
            shots_total=0,
            shots_total_home=0,
            shots_total_away=0,
            shots_on_goal=0,
            shots_on_goal_home=0,
            shots_on_goal_away=0,
            corners=0,
            corners_home=0,
            corners_away=0,
            fouls=0,
            fouls_home=0,
            fouls_away=0,
            yellow_cards=0,
            yellow_cards_home=0,
            yellow_cards_away=0,
            red_cards=0,
            red_cards_home=0,
            red_cards_away=0,
            passes_total=0,
            passes_total_home=0,
            passes_total_away=0,
            passes_accurate=0,
            passes_accurate_home=0,
            passes_accurate_away=0,
            pass_accuracy_pct=None,
            events_goals=0,
            events_goals_home=0,
            events_goals_away=0,
            events_yellow_cards=0,
            events_yellow_cards_home=0,
            events_yellow_cards_away=0,
            events_red_cards=0,
            events_red_cards_home=0,
            events_red_cards_away=0,
            events_substitutions=0,
            events_substitutions_home=0,
            events_substitutions_away=0,
            last_matches=[],
        )

    played = won = drawn = lost = points = 0
    goals_for = goals_against = 0
    goals_for_home = goals_against_home = 0
    goals_for_away = goals_against_away = 0
    home_played = home_points = away_played = away_points = 0
    form_list: list[str] = []
    last_matches: list[TeamLastMatchOut] = []

    fixture_ids = [f.id for f in fixtures]
    fixture_is_home = {f.id: (f.home_team_id == team_id) for f in fixtures}

    stats_result = await db.execute(
        select(FixtureStatistics).where(
            FixtureStatistics.fixture_id.in_(fixture_ids),
            FixtureStatistics.team_id == team_id,
        )
    )
    stats_rows = stats_result.scalars().all()

    events_result = await db.execute(
        select(FixtureEvent).where(
            FixtureEvent.fixture_id.in_(fixture_ids),
            FixtureEvent.team_id == team_id,
        )
    )
    event_rows = events_result.scalars().all()

    for f in fixtures:
        is_home = f.home_team_id == team_id
        opponent = f.away_team if is_home else f.home_team
        gf = f.home_score if is_home else f.away_score
        ga = f.away_score if is_home else f.home_score

        if gf is None or ga is None:
            continue

        played += 1
        goals_for += gf
        goals_against += ga

        if gf > ga:
            result_symbol = "W"
            won += 1
        elif gf == ga:
            result_symbol = "D"
            drawn += 1
        else:
            result_symbol = "L"
            lost += 1
        points += _points_for_result(result_symbol)
        form_list.append(result_symbol)

        if is_home:
            home_played += 1
            home_points += _points_for_result(result_symbol)
            goals_for_home += gf
            goals_against_home += ga
        else:
            away_played += 1
            away_points += _points_for_result(result_symbol)
            goals_for_away += gf
            goals_against_away += ga

        last_matches.append(
            TeamLastMatchOut(
                fixture_id=f.id,
                kickoff_utc=f.kickoff_utc.isoformat() if f.kickoff_utc else None,
                league_id=f.league_id,
                opponent_team_id=opponent.id if opponent else 0,
                opponent_team_name=opponent.name if opponent else "Unbekannt",
                is_home=is_home,
                goals_for=gf,
                goals_against=ga,
                result=result_symbol,
            )
        )

    xg_total = 0.0
    xg_total_home = 0.0
    xg_total_away = 0.0
    xg_seen = False
    xg_home_seen = False
    xg_away_seen = False
    possession_sum = 0.0
    possession_count = 0
    possession_sum_home = 0.0
    possession_count_home = 0
    possession_sum_away = 0.0
    possession_count_away = 0
    shots_total = shots_on_goal = corners = fouls = 0
    shots_total_home = shots_on_goal_home = corners_home = fouls_home = 0
    shots_total_away = shots_on_goal_away = corners_away = fouls_away = 0
    yellow_cards = red_cards = 0
    yellow_cards_home = red_cards_home = 0
    yellow_cards_away = red_cards_away = 0
    passes_total = passes_accurate = 0
    passes_total_home = passes_accurate_home = 0
    passes_total_away = passes_accurate_away = 0

    for s in stats_rows:
        is_home = fixture_is_home.get(s.fixture_id, False)
        if s.expected_goals is not None:
            xg_total += float(s.expected_goals)
            xg_seen = True
            if is_home:
                xg_total_home += float(s.expected_goals)
                xg_home_seen = True
            else:
                xg_total_away += float(s.expected_goals)
                xg_away_seen = True
        if s.ball_possession is not None:
            pos = float(s.ball_possession)
            possession_sum += pos
            possession_count += 1
            if is_home:
                possession_sum_home += pos
                possession_count_home += 1
            else:
                possession_sum_away += pos
                possession_count_away += 1
        shots_total += s.shots_total or 0
        shots_on_goal += s.shots_on_goal or 0
        corners += s.corner_kicks or 0
        fouls += s.fouls or 0
        yellow_cards += s.yellow_cards or 0
        red_cards += s.red_cards or 0
        passes_total += s.passes_total or 0
        passes_accurate += s.passes_accurate or 0
        if is_home:
            shots_total_home += s.shots_total or 0
            shots_on_goal_home += s.shots_on_goal or 0
            corners_home += s.corner_kicks or 0
            fouls_home += s.fouls or 0
            yellow_cards_home += s.yellow_cards or 0
            red_cards_home += s.red_cards or 0
            passes_total_home += s.passes_total or 0
            passes_accurate_home += s.passes_accurate or 0
        else:
            shots_total_away += s.shots_total or 0
            shots_on_goal_away += s.shots_on_goal or 0
            corners_away += s.corner_kicks or 0
            fouls_away += s.fouls or 0
            yellow_cards_away += s.yellow_cards or 0
            red_cards_away += s.red_cards or 0
            passes_total_away += s.passes_total or 0
            passes_accurate_away += s.passes_accurate or 0

    events_goals = 0
    events_goals_home = events_goals_away = 0
    events_yellow_cards = 0
    events_yellow_cards_home = events_yellow_cards_away = 0
    events_red_cards = 0
    events_red_cards_home = events_red_cards_away = 0
    events_substitutions = 0
    events_substitutions_home = events_substitutions_away = 0
    for e in event_rows:
        is_home = fixture_is_home.get(e.fixture_id, False)
        if e.event_type == "Goal":
            events_goals += 1
            if is_home:
                events_goals_home += 1
            else:
                events_goals_away += 1
        if e.detail == "Yellow Card":
            events_yellow_cards += 1
            if is_home:
                events_yellow_cards_home += 1
            else:
                events_yellow_cards_away += 1
        if e.detail in {"Red Card", "Second Yellow card"}:
            events_red_cards += 1
            if is_home:
                events_red_cards_home += 1
            else:
                events_red_cards_away += 1
        if e.event_type == "subst":
            events_substitutions += 1
            if is_home:
                events_substitutions_home += 1
            else:
                events_substitutions_away += 1

    goal_diff = goals_for - goals_against
    avg_goals_for = round(goals_for / played, 2) if played else 0.0
    avg_goals_against = round(goals_against / played, 2) if played else 0.0
    pass_accuracy_pct = round((passes_accurate / passes_total) * 100, 2) if passes_total else None
    avg_ball_possession = round(possession_sum / possession_count, 2) if possession_count else None
    avg_ball_possession_home = round(possession_sum_home / possession_count_home, 2) if possession_count_home else None
    avg_ball_possession_away = round(possession_sum_away / possession_count_away, 2) if possession_count_away else None

    return TeamSummaryOut(
        team_id=team.id,
        team_name=team.name,
        team_logo_url=team.logo_url,
        season_year=season_year,
        league_id=league_id,
        played=played,
        won=won,
        drawn=drawn,
        lost=lost,
        points=points,
        goals_for=goals_for,
        goals_against=goals_against,
        goal_diff=goal_diff,
        goals_for_home=goals_for_home,
        goals_against_home=goals_against_home,
        goals_for_away=goals_for_away,
        goals_against_away=goals_against_away,
        form="".join(form_list[-5:]),
        home_played=home_played,
        home_points=home_points,
        away_played=away_played,
        away_points=away_points,
        avg_goals_for=avg_goals_for,
        avg_goals_against=avg_goals_against,
        xg_total=round(xg_total, 2) if xg_seen else None,
        xg_total_home=round(xg_total_home, 2) if xg_home_seen else None,
        xg_total_away=round(xg_total_away, 2) if xg_away_seen else None,
        avg_ball_possession=avg_ball_possession,
        avg_ball_possession_home=avg_ball_possession_home,
        avg_ball_possession_away=avg_ball_possession_away,
        shots_total=shots_total,
        shots_total_home=shots_total_home,
        shots_total_away=shots_total_away,
        shots_on_goal=shots_on_goal,
        shots_on_goal_home=shots_on_goal_home,
        shots_on_goal_away=shots_on_goal_away,
        corners=corners,
        corners_home=corners_home,
        corners_away=corners_away,
        fouls=fouls,
        fouls_home=fouls_home,
        fouls_away=fouls_away,
        yellow_cards=yellow_cards,
        yellow_cards_home=yellow_cards_home,
        yellow_cards_away=yellow_cards_away,
        red_cards=red_cards,
        red_cards_home=red_cards_home,
        red_cards_away=red_cards_away,
        passes_total=passes_total,
        passes_total_home=passes_total_home,
        passes_total_away=passes_total_away,
        passes_accurate=passes_accurate,
        passes_accurate_home=passes_accurate_home,
        passes_accurate_away=passes_accurate_away,
        pass_accuracy_pct=pass_accuracy_pct,
        events_goals=events_goals,
        events_goals_home=events_goals_home,
        events_goals_away=events_goals_away,
        events_yellow_cards=events_yellow_cards,
        events_yellow_cards_home=events_yellow_cards_home,
        events_yellow_cards_away=events_yellow_cards_away,
        events_red_cards=events_red_cards,
        events_red_cards_home=events_red_cards_home,
        events_red_cards_away=events_red_cards_away,
        events_substitutions=events_substitutions,
        events_substitutions_home=events_substitutions_home,
        events_substitutions_away=events_substitutions_away,
        last_matches=last_matches[-8:][::-1],
    )


@router.get("/{team_id}/elo", response_model=TeamEloOut)
async def team_elo(
    team_id: int,
    season_year: int = Query(..., description="Saison-Jahr, z.B. 2025"),
    league_id: int = Query(..., description="Liga-ID, z.B. 78"),
    db: AsyncSession = Depends(get_db),
):
    team = await db.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    row = await db.execute(
        select(TeamEloSnapshot).where(
            TeamEloSnapshot.team_id == team_id,
            TeamEloSnapshot.league_id == league_id,
            TeamEloSnapshot.season_year == season_year,
        )
    )
    snap = row.scalar_one_or_none()

    if snap is None:
        await recompute_team_elo_for_league(db, league_id=league_id, season_year=season_year)
        row = await db.execute(
            select(TeamEloSnapshot).where(
                TeamEloSnapshot.team_id == team_id,
                TeamEloSnapshot.league_id == league_id,
                TeamEloSnapshot.season_year == season_year,
            )
        )
        snap = row.scalar_one_or_none()

    if snap is None:
        raise HTTPException(status_code=404, detail="No Elo data for this team/league/season")

    return TeamEloOut(
        team_id=team.id,
        team_name=team.name,
        team_logo_url=team.logo_url,
        league_id=snap.league_id,
        season_year=snap.season_year,
        elo_overall=float(snap.elo_overall),
        elo_home=float(snap.elo_home),
        elo_away=float(snap.elo_away),
        games_played=snap.games_played,
        games_home=snap.games_home,
        games_away=snap.games_away,
        elo_delta_last_5=float(snap.elo_delta_last_5),
        strength_tier=snap.strength_tier,
        computed_at=snap.computed_at.isoformat() if snap.computed_at else None,
        model_version=snap.model_version,
    )


@router.get("/{team_id}/form", response_model=TeamFormOut)
async def team_form(
    team_id: int,
    season_year: int = Query(..., description="Saison-Jahr, z.B. 2025"),
    league_id: int = Query(..., description="Liga-ID, z.B. 78"),
    window_size: int = Query(5, ge=3, le=20),
    db: AsyncSession = Depends(get_db),
):
    team = await db.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    rows = await db.execute(
        select(TeamFormSnapshot).where(
            TeamFormSnapshot.team_id == team_id,
            TeamFormSnapshot.league_id == league_id,
            TeamFormSnapshot.season_year == season_year,
            TeamFormSnapshot.window_size == window_size,
        )
    )
    snaps = rows.scalars().all()
    if not snaps:
        await recompute_team_form_for_league(
            db=db,
            league_id=league_id,
            season_year=season_year,
            window_size=window_size,
        )
        rows = await db.execute(
            select(TeamFormSnapshot).where(
                TeamFormSnapshot.team_id == team_id,
                TeamFormSnapshot.league_id == league_id,
                TeamFormSnapshot.season_year == season_year,
                TeamFormSnapshot.window_size == window_size,
            )
        )
        snaps = rows.scalars().all()

    if not snaps:
        raise HTTPException(status_code=404, detail="No form data for this team/league/season/window")

    snaps = sorted(snaps, key=lambda x: {"overall": 0, "home": 1, "away": 2}.get(x.scope, 99))
    return TeamFormOut(
        team_id=team.id,
        team_name=team.name,
        team_logo_url=team.logo_url,
        league_id=league_id,
        season_year=season_year,
        window_size=window_size,
        scopes=[
            TeamFormScopeOut(
                scope=s.scope,
                form_score=float(s.form_score),
                result_score=float(s.result_score),
                performance_score=float(s.performance_score),
                trend_score=float(s.trend_score),
                opponent_strength_score=float(s.opponent_strength_score),
                elo_adjusted_result_score=float(s.elo_adjusted_result_score),
                form_trend=s.form_trend,
                form_bucket=s.form_bucket,
                games_considered=s.games_considered,
                computed_at=s.computed_at.isoformat() if s.computed_at else None,
                model_version=s.model_version,
            )
            for s in snaps
        ],
    )
