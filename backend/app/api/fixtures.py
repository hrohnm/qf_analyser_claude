from datetime import date
import math
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.fixture import Fixture
from app.models.fixture_events import FixtureEvent
from app.models.fixture_goal_probability import FixtureGoalProbability
from app.models.fixture_injury import FixtureInjury
from app.models.fixture_injury_impact import FixtureInjuryImpact
from app.models.fixture_prediction import FixturePrediction
from app.models.fixture_odds import FixtureOdds
from app.models.fixture_statistics import FixtureStatistics
from app.models.league import League
from app.models.team import Team
from app.models.team_elo_snapshot import TeamEloSnapshot
from app.models.team_form_snapshot import TeamFormSnapshot
from app.services.goal_probability_service import recompute_goal_probability_for_fixture
from app.services.injury_impact_service import recompute_fixture_injury_impacts
from app.sync.leagues_config import LEAGUES

router = APIRouter(prefix="/fixtures", tags=["Fixtures"])

LEAGUE_META: dict[int, dict] = {l["id"]: l for l in LEAGUES}


class FixtureOut(BaseModel):
    id: int
    league_id: int
    league_name: str | None = None
    league_country: str | None = None
    league_tier: int | None = None
    season_year: int
    home_team_id: int
    away_team_id: int
    home_team_name: str | None = None
    away_team_name: str | None = None
    kickoff_utc: str | None = None
    round: str | None = None
    matchday: int | None = None
    status_short: str | None = None
    home_score: int | None = None
    away_score: int | None = None
    home_ht_score: int | None = None
    away_ht_score: int | None = None
    venue_name: str | None = None

    model_config = {"from_attributes": True}


class FixtureStatisticOut(BaseModel):
    team_id: int
    team_name: str | None = None
    team_logo_url: str | None = None
    shots_on_goal: int | None = None
    shots_off_goal: int | None = None
    shots_total: int | None = None
    shots_blocked: int | None = None
    shots_inside_box: int | None = None
    shots_outside_box: int | None = None
    fouls: int | None = None
    corner_kicks: int | None = None
    offsides: int | None = None
    ball_possession: float | None = None
    yellow_cards: int | None = None
    red_cards: int | None = None
    goalkeeper_saves: int | None = None
    passes_total: int | None = None
    passes_accurate: int | None = None
    pass_accuracy: float | None = None
    expected_goals: float | None = None


class FixtureEventOut(BaseModel):
    id: int
    team_id: int
    team_name: str | None = None
    elapsed: int | None = None
    elapsed_extra: int | None = None
    event_type: str | None = None
    detail: str | None = None
    comments: str | None = None
    player_id: int | None = None
    player_name: str | None = None
    assist_id: int | None = None
    assist_name: str | None = None


class FixtureDetailsOut(BaseModel):
    fixture: FixtureOut
    prediction: dict | None = None
    goal_probability_home: dict | None = None
    goal_probability_away: dict | None = None
    concede_probability_home: dict | None = None
    concede_probability_away: dict | None = None
    match_goal_lines: dict | None = None
    injuries: list[dict]
    injury_impacts: list[dict]
    team_injury_impact_home: float = 0.0
    team_injury_impact_away: float = 0.0
    statistics: list[FixtureStatisticOut]
    events: list[FixtureEventOut]
    odds: list[dict] = []


def _to_out(f: Fixture, league: League | None = None) -> FixtureOut:
    meta = LEAGUE_META.get(f.league_id, {})
    return FixtureOut(
        id=f.id,
        league_id=f.league_id,
        league_name=league.name if league else meta.get("name"),
        league_country=league.country if league else meta.get("country"),
        league_tier=league.tier if league else meta.get("tier"),
        season_year=f.season_year,
        home_team_id=f.home_team_id,
        away_team_id=f.away_team_id,
        home_team_name=f.home_team.name if f.home_team else None,
        away_team_name=f.away_team.name if f.away_team else None,
        kickoff_utc=f.kickoff_utc.isoformat() if f.kickoff_utc else None,
        round=f.round,
        matchday=f.matchday,
        status_short=f.status_short,
        home_score=f.home_score,
        away_score=f.away_score,
        home_ht_score=f.home_ht_score,
        away_ht_score=f.away_ht_score,
        venue_name=f.venue_name,
    )


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _poisson_ge(lmbd: float, at_least: int) -> float:
    if at_least <= 0:
        return 1.0
    s = 0.0
    for k in range(at_least):
        s += math.exp(-lmbd) * (lmbd ** k) / math.factorial(k)
    return _clamp(1.0 - s, 0.0, 1.0)


@router.get("/{fixture_id}/details", response_model=FixtureDetailsOut)
async def fixture_details(
    fixture_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Details zu einem Spiel: Fixture-Basisdaten, Team-Statistiken und Events."""
    fixture_result = await db.execute(
        select(Fixture, League)
        .join(League, League.id == Fixture.league_id)
        .options(selectinload(Fixture.home_team), selectinload(Fixture.away_team))
        .where(Fixture.id == fixture_id)
    )
    row = fixture_result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Fixture not found")
    fixture, league = row

    stats_result = await db.execute(
        select(FixtureStatistics, Team)
        .outerjoin(Team, Team.id == FixtureStatistics.team_id)
        .where(FixtureStatistics.fixture_id == fixture_id)
    )
    statistics = []
    for stat, team in stats_result.all():
        statistics.append(FixtureStatisticOut(
            team_id=stat.team_id,
            team_name=team.name if team else None,
            team_logo_url=team.logo_url if team else None,
            shots_on_goal=stat.shots_on_goal,
            shots_off_goal=stat.shots_off_goal,
            shots_total=stat.shots_total,
            shots_blocked=stat.shots_blocked,
            shots_inside_box=stat.shots_inside_box,
            shots_outside_box=stat.shots_outside_box,
            fouls=stat.fouls,
            corner_kicks=stat.corner_kicks,
            offsides=stat.offsides,
            ball_possession=float(stat.ball_possession) if stat.ball_possession is not None else None,
            yellow_cards=stat.yellow_cards,
            red_cards=stat.red_cards,
            goalkeeper_saves=stat.goalkeeper_saves,
            passes_total=stat.passes_total,
            passes_accurate=stat.passes_accurate,
            pass_accuracy=float(stat.pass_accuracy) if stat.pass_accuracy is not None else None,
            expected_goals=float(stat.expected_goals) if stat.expected_goals is not None else None,
        ))

    events_result = await db.execute(
        select(FixtureEvent, Team)
        .outerjoin(Team, Team.id == FixtureEvent.team_id)
        .where(FixtureEvent.fixture_id == fixture_id)
        .order_by(FixtureEvent.elapsed, FixtureEvent.elapsed_extra, FixtureEvent.id)
    )
    events = []
    for event, team in events_result.all():
        events.append(FixtureEventOut(
            id=event.id,
            team_id=event.team_id,
            team_name=team.name if team else None,
            elapsed=event.elapsed,
            elapsed_extra=event.elapsed_extra,
            event_type=event.event_type,
            detail=event.detail,
            comments=event.comments,
            player_id=event.player_id,
            player_name=event.player_name,
            assist_id=event.assist_id,
            assist_name=event.assist_name,
        ))

    prediction_row = await db.execute(
        select(FixturePrediction).where(FixturePrediction.fixture_id == fixture_id)
    )
    prediction = prediction_row.scalar_one_or_none()
    prediction_out = None
    if prediction:
        prediction_out = {
            "winner_team_id": prediction.winner_team_id,
            "winner_name": prediction.winner_name,
            "winner_comment": prediction.winner_comment,
            "win_or_draw": prediction.win_or_draw,
            "under_over": prediction.under_over,
            "advice": prediction.advice,
            "percent_home": float(prediction.percent_home) if prediction.percent_home is not None else None,
            "percent_draw": float(prediction.percent_draw) if prediction.percent_draw is not None else None,
            "percent_away": float(prediction.percent_away) if prediction.percent_away is not None else None,
            "fetched_at": prediction.fetched_at.isoformat() if prediction.fetched_at else None,
        }

    injuries_result = await db.execute(
        select(FixtureInjury)
        .where(FixtureInjury.fixture_id == fixture_id)
        .order_by(FixtureInjury.team_name, FixtureInjury.player_name)
    )
    injuries = [
        {
            "team_id": i.team_id,
            "team_name": i.team_name,
            "player_id": i.player_id,
            "player_name": i.player_name,
            "injury_type": i.injury_type,
            "injury_reason": i.injury_reason,
            "fetched_at": i.fetched_at.isoformat() if i.fetched_at else None,
        }
        for i in injuries_result.scalars().all()
    ]

    gp_result = await db.execute(
        select(FixtureGoalProbability)
        .where(FixtureGoalProbability.fixture_id == fixture_id)
        .order_by(FixtureGoalProbability.is_home.desc())
    )
    gp_rows = gp_result.scalars().all()
    if not gp_rows and fixture.status_short in {"NS", "TBD", "PST", "1H", "HT", "2H"}:
        await recompute_goal_probability_for_fixture(db, fixture_id)
        gp_result = await db.execute(
            select(FixtureGoalProbability)
            .where(FixtureGoalProbability.fixture_id == fixture_id)
            .order_by(FixtureGoalProbability.is_home.desc())
        )
        gp_rows = gp_result.scalars().all()

    gp_home = next((r for r in gp_rows if r.team_id == fixture.home_team_id), None)
    gp_away = next((r for r in gp_rows if r.team_id == fixture.away_team_id), None)

    def _gp_to_dict(row: FixtureGoalProbability | None) -> dict | None:
        if row is None:
            return None
        return {
            "team_id": row.team_id,
            "is_home": row.is_home,
            "lambda_weighted": float(row.lambda_weighted),
            "p_ge_1_goal": float(row.p_ge_1_goal),
            "p_ge_2_goals": float(row.p_ge_2_goals),
            "p_ge_3_goals": float(row.p_ge_3_goals),
            "confidence": float(row.confidence),
            "sample_size": row.sample_size,
            "computed_at": row.computed_at.isoformat() if row.computed_at else None,
            "model_version": row.model_version,
        }

    elo_rows = await db.execute(
        select(TeamEloSnapshot).where(
            TeamEloSnapshot.league_id == fixture.league_id,
            TeamEloSnapshot.season_year == fixture.season_year,
            TeamEloSnapshot.team_id.in_([fixture.home_team_id, fixture.away_team_id]),
        )
    )
    elo_map = {e.team_id: e for e in elo_rows.scalars().all()}

    form_rows = await db.execute(
        select(TeamFormSnapshot).where(
            TeamFormSnapshot.league_id == fixture.league_id,
            TeamFormSnapshot.season_year == fixture.season_year,
            TeamFormSnapshot.window_size == 5,
            TeamFormSnapshot.team_id.in_([fixture.home_team_id, fixture.away_team_id]),
            TeamFormSnapshot.scope.in_(["home", "away"]),
        )
    )
    form_map: dict[tuple[int, str], TeamFormSnapshot] = {
        (f.team_id, f.scope): f for f in form_rows.scalars().all()
    }

    match_goal_lines = None
    if gp_home is not None and gp_away is not None:
        base_home_lambda = float(gp_home.lambda_weighted)
        base_away_lambda = float(gp_away.lambda_weighted)

        home_elo = float(elo_map[fixture.home_team_id].elo_overall) if fixture.home_team_id in elo_map else 1500.0
        away_elo = float(elo_map[fixture.away_team_id].elo_overall) if fixture.away_team_id in elo_map else 1500.0
        elo_diff = home_elo - away_elo

        home_form = form_map.get((fixture.home_team_id, "home"))
        away_form = form_map.get((fixture.away_team_id, "away"))
        home_form_score = float(home_form.form_score) if home_form else 50.0
        away_form_score = float(away_form.form_score) if away_form else 50.0
        form_diff = home_form_score - away_form_score

        # Factors:
        # - explicit home advantage
        # - elo relative strength
        # - current scoped form
        home_adv_factor = 1.06
        away_adv_factor = 0.94
        elo_factor_home = _clamp(1.0 + (elo_diff / 4000.0), 0.90, 1.10)
        elo_factor_away = _clamp(1.0 - (elo_diff / 4000.0), 0.90, 1.10)
        form_factor_home = _clamp(1.0 + (form_diff / 500.0), 0.90, 1.10)
        form_factor_away = _clamp(1.0 - (form_diff / 500.0), 0.90, 1.10)

        lambda_home_final = _clamp(base_home_lambda * home_adv_factor * elo_factor_home * form_factor_home, 0.05, 5.0)
        lambda_away_final = _clamp(base_away_lambda * away_adv_factor * elo_factor_away * form_factor_away, 0.05, 5.0)

        match_goal_lines = {
            "home": {
                "plus_0_5": round(_poisson_ge(lambda_home_final, 1), 4),
                "plus_1_5": round(_poisson_ge(lambda_home_final, 2), 4),
                "lambda_base": round(base_home_lambda, 4),
                "lambda_final": round(lambda_home_final, 4),
                "factors": {
                    "home_advantage": home_adv_factor,
                    "elo": round(elo_factor_home, 4),
                    "form": round(form_factor_home, 4),
                },
            },
            "away": {
                "plus_0_5": round(_poisson_ge(lambda_away_final, 1), 4),
                "plus_1_5": round(_poisson_ge(lambda_away_final, 2), 4),
                "lambda_base": round(base_away_lambda, 4),
                "lambda_final": round(lambda_away_final, 4),
                "factors": {
                    "home_advantage": away_adv_factor,
                    "elo": round(elo_factor_away, 4),
                    "form": round(form_factor_away, 4),
                },
            },
        }

    impacts_result = await db.execute(
        select(FixtureInjuryImpact)
        .where(FixtureInjuryImpact.fixture_id == fixture_id)
        .order_by(FixtureInjuryImpact.impact_score.desc())
    )
    impacts_rows = impacts_result.scalars().all()
    if injuries and not impacts_rows:
        await recompute_fixture_injury_impacts(db, fixture_id)
        impacts_result = await db.execute(
            select(FixtureInjuryImpact)
            .where(FixtureInjuryImpact.fixture_id == fixture_id)
            .order_by(FixtureInjuryImpact.impact_score.desc())
        )
        impacts_rows = impacts_result.scalars().all()
    impacts = [
        {
            "team_id": i.team_id,
            "player_id": i.player_id,
            "player_name": i.player_name,
            "impact_score": float(i.impact_score),
            "impact_bucket": i.impact_bucket,
            "importance_score": float(i.importance_score),
            "contribution_score": float(i.contribution_score),
            "replaceability_score": float(i.replaceability_score),
            "availability_factor": float(i.availability_factor),
            "confidence": float(i.confidence),
            "model_version": i.model_version,
            "computed_at": i.computed_at.isoformat() if i.computed_at else None,
        }
        for i in impacts_rows
    ]

    home_impact = round(
        sum(i["impact_score"] for i in impacts if i.get("team_id") == fixture.home_team_id),
        2,
    )
    away_impact = round(
        sum(i["impact_score"] for i in impacts if i.get("team_id") == fixture.away_team_id),
        2,
    )

    odds_result = await db.execute(
        select(FixtureOdds)
        .where(FixtureOdds.fixture_id == fixture_id)
        .order_by(FixtureOdds.bookmaker_id, FixtureOdds.bet_id)
    )
    odds = [
        {
            "bookmaker_id": o.bookmaker_id,
            "bookmaker_name": o.bookmaker_name,
            "bet_id": o.bet_id,
            "bet_name": o.bet_name,
            "values": o.values,
            "updated_at": o.updated_at.isoformat() if o.updated_at else None,
        }
        for o in odds_result.scalars().all()
    ]

    return FixtureDetailsOut(
        fixture=_to_out(fixture, league),
        prediction=prediction_out,
        goal_probability_home=_gp_to_dict(gp_home),
        goal_probability_away=_gp_to_dict(gp_away),
        concede_probability_home=_gp_to_dict(gp_away),
        concede_probability_away=_gp_to_dict(gp_home),
        match_goal_lines=match_goal_lines,
        injuries=injuries,
        injury_impacts=impacts,
        team_injury_impact_home=home_impact,
        team_injury_impact_away=away_impact,
        statistics=statistics,
        events=events,
        odds=odds,
    )


@router.get("/today", response_model=list[FixtureOut])
async def fixtures_today(
    for_date: date | None = Query(None, description="Datum (YYYY-MM-DD), Standard: heute"),
    db: AsyncSession = Depends(get_db),
):
    """Alle Spiele unserer 18 Ligen für einen bestimmten Tag, sortiert nach Anstoß."""
    target = for_date or date.today()
    stmt = (
        select(Fixture, League)
        .join(League, League.id == Fixture.league_id)
        .options(selectinload(Fixture.home_team), selectinload(Fixture.away_team))
        .where(cast(Fixture.kickoff_utc, Date) == target)
        .order_by(Fixture.kickoff_utc)
    )
    result = await db.execute(stmt)
    return [_to_out(f, league) for f, league in result.all()]


@router.get("/", response_model=list[FixtureOut])
async def list_fixtures(
    league_id: int | None = Query(None),
    season_year: int | None = Query(None),
    status: str | None = Query(None),
    matchday: int | None = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
):
    """Spiele aus der lokalen Datenbank mit optionalen Filtern."""
    stmt = (
        select(Fixture, League)
        .join(League, League.id == Fixture.league_id)
        .options(selectinload(Fixture.home_team), selectinload(Fixture.away_team))
        .order_by(Fixture.kickoff_utc)
        .limit(limit)
        .offset(offset)
    )
    if league_id:
        stmt = stmt.where(Fixture.league_id == league_id)
    if season_year:
        stmt = stmt.where(Fixture.season_year == season_year)
    if status:
        stmt = stmt.where(Fixture.status_short == status)
    if matchday:
        stmt = stmt.where(Fixture.matchday == matchday)

    result = await db.execute(stmt)
    return [_to_out(f, league) for f, league in result.all()]
