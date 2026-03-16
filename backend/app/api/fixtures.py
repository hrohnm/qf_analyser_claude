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
from app.models.fixture_h2h import FixtureH2H
from app.models.fixture_injury import FixtureInjury
from app.models.fixture_injury_impact import FixtureInjuryImpact
from app.models.fixture_prediction import FixturePrediction
from app.models.fixture_statistics import FixtureStatistics
from app.models.fixture_top_scorer_pattern import FixtureTopScorerPattern
from app.models.league import League
from app.models.team import Team
from app.models.team_elo_snapshot import TeamEloSnapshot
from app.models.team_form_snapshot import TeamFormSnapshot
from app.models.team_goal_timing import TeamGoalTiming
from app.models.team_home_advantage import TeamHomeAdvantage
from app.services.goal_probability_service import recompute_goal_probability_for_fixture
from app.services.h2h_service import MIN_MATCHES as H2H_MIN_MATCHES, compute_h2h_for_fixture
from app.services.injury_impact_service import recompute_fixture_injury_impacts
from app.services.ai_picks_service import generate_ai_picks
from app.services.top_scorer_service import compute_top_scorer_for_fixture
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
    elapsed: int | None = None
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
    # New pattern data
    h2h: dict | None = None
    goal_timing_home: dict | None = None
    goal_timing_away: dict | None = None
    home_advantage_home: dict | None = None
    home_advantage_away: dict | None = None
    scoreline_distribution: dict | None = None
    match_result_probability: dict | None = None
    pattern_predictions: dict | None = None
    value_bets: list[dict] | None = None
    pattern_evaluation: dict | None = None
    top_scorer_pattern: dict | None = None


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
        elapsed=f.elapsed,
        home_score=f.home_score,
        away_score=f.away_score,
        home_ht_score=f.home_ht_score,
        away_ht_score=f.away_ht_score,
        venue_name=f.venue_name,
    )


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _binary_signal(prob_yes: float | None, market: str, yes_label: str, no_label: str, threshold: float, min_confidence: float) -> dict | None:
    if prob_yes is None:
        return None
    if prob_yes >= threshold:
        pick = yes_label
        probability = prob_yes
    else:
        pick = no_label
        probability = 1.0 - prob_yes
    confidence = _clamp(probability, 0.0, 1.0)
    emitted = confidence >= min_confidence
    return {
        "market": market,
        "pick": pick,
        "probability": round(probability, 4),
        "raw_probability": round(prob_yes, 4),
        "confidence": round(confidence, 4),
        "threshold": round(threshold, 4),
        "emitted": emitted,
    }


def _outcome_signal(p_home: float | None, p_draw: float | None, p_away: float | None, home_label: str, away_label: str) -> dict | None:
    if p_home is None or p_draw is None or p_away is None:
        return None
    options = [
        {"pick": home_label, "prob": p_home},
        {"pick": "Unentschieden", "prob": p_draw},
        {"pick": away_label, "prob": p_away},
    ]
    options.sort(key=lambda x: x["prob"], reverse=True)
    best = options[0]
    second = options[1]
    margin = best["prob"] - second["prob"]
    confidence = _clamp((0.65 * best["prob"]) + (0.35 * min(1.0, margin / 0.20)), 0.0, 1.0)
    emitted = confidence >= 0.58 and margin >= 0.06
    return {
        "market": "1X2",
        "pick": best["pick"],
        "probability": round(best["prob"], 4),
        "confidence": round(confidence, 4),
        "margin": round(margin, 4),
        "emitted": emitted,
    }


def _double_chance_signal(p_home: float | None, p_draw: float | None, p_away: float | None) -> dict | None:
    if p_home is None or p_draw is None or p_away is None:
        return None
    options = [
        {"pick": "1X", "prob": p_home + p_draw},
        {"pick": "X2", "prob": p_draw + p_away},
        {"pick": "12", "prob": p_home + p_away},
    ]
    options.sort(key=lambda x: x["prob"], reverse=True)
    best = options[0]
    second = options[1]
    confidence = _clamp(best["prob"], 0.0, 1.0)
    emitted = confidence >= 0.68 and (best["prob"] - second["prob"]) >= 0.04
    return {
        "market": "DC",
        "pick": best["pick"],
        "probability": round(best["prob"], 4),
        "confidence": round(confidence, 4),
        "margin": round(best["prob"] - second["prob"], 4),
        "emitted": emitted,
    }


def _build_pattern_predictions(
    fixture: Fixture,
    mrp_out: dict | None,
    scoreline_out: dict | None,
    gp_home: dict | None,
    gp_away: dict | None,
) -> dict | None:
    p_home = mrp_out["p_home_win"] if mrp_out else (scoreline_out["p_home_win"] if scoreline_out else None)
    p_draw = mrp_out["p_draw"] if mrp_out else (scoreline_out["p_draw"] if scoreline_out else None)
    p_away = mrp_out["p_away_win"] if mrp_out else (scoreline_out["p_away_win"] if scoreline_out else None)
    p_btts = mrp_out["p_btts"] if mrp_out else (scoreline_out["p_btts"] if scoreline_out else None)
    p_over_15 = mrp_out["p_over_15"] if mrp_out else (scoreline_out["p_over_15"] if scoreline_out else None)
    p_over_25 = mrp_out["p_over_25"] if mrp_out else (scoreline_out["p_over_25"] if scoreline_out else None)
    p_home_scores = gp_home["p_ge_1_goal"] if gp_home else None
    p_away_scores = gp_away["p_ge_1_goal"] if gp_away else None

    predictions = {
        "one_x_two": _outcome_signal(
            p_home, p_draw, p_away,
            fixture.home_team.name if fixture.home_team else "Heim",
            fixture.away_team.name if fixture.away_team else "Gast",
        ),
        "double_chance": _double_chance_signal(p_home, p_draw, p_away),
        "over_15": _binary_signal(p_over_15, "Over 1.5", "Ja", "Nein", 0.55, 0.67),
        "over_25": _binary_signal(p_over_25, "Over 2.5", "Ja", "Nein", 0.50, 0.62),
        "btts": _binary_signal(p_btts, "BTTS", "Ja", "Nein", 0.50, 0.62),
        "home_scores": _binary_signal(p_home_scores, "Home scores", "Ja", "Nein", 0.50, 0.64),
        "away_scores": _binary_signal(p_away_scores, "Away scores", "Ja", "Nein", 0.50, 0.64),
    }
    return predictions if any(v is not None for v in predictions.values()) else None


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
        def _pf(v) -> float | None:
            return float(v) if v is not None else None

        prediction_out = {
            # Core
            "winner_team_id": prediction.winner_team_id,
            "winner_name": prediction.winner_name,
            "winner_comment": prediction.winner_comment,
            "win_or_draw": prediction.win_or_draw,
            "under_over": prediction.under_over,
            "advice": prediction.advice,
            "percent_home": _pf(prediction.percent_home),
            "percent_draw": _pf(prediction.percent_draw),
            "percent_away": _pf(prediction.percent_away),
            "goals_pred_home": prediction.goals_pred_home,
            "goals_pred_away": prediction.goals_pred_away,
            # Comparison (API-Football's analytical scores)
            "comparison": {
                "form":    {"home": _pf(prediction.cmp_form_home),    "away": _pf(prediction.cmp_form_away)},
                "att":     {"home": _pf(prediction.cmp_att_home),     "away": _pf(prediction.cmp_att_away)},
                "def":     {"home": _pf(prediction.cmp_def_home),     "away": _pf(prediction.cmp_def_away)},
                "poisson": {"home": _pf(prediction.cmp_poisson_home), "away": _pf(prediction.cmp_poisson_away)},
                "h2h":     {"home": _pf(prediction.cmp_h2h_home),     "away": _pf(prediction.cmp_h2h_away)},
                "goals":   {"home": _pf(prediction.cmp_goals_home),   "away": _pf(prediction.cmp_goals_away)},
                "total":   {"home": _pf(prediction.cmp_total_home),   "away": _pf(prediction.cmp_total_away)},
            },
            # Last 5
            "home_last5": {
                "form": _pf(prediction.home_last5_form),
                "att":  _pf(prediction.home_last5_att),
                "def":  _pf(prediction.home_last5_def),
                "goals_for_avg":     _pf(prediction.home_last5_goals_for_avg),
                "goals_against_avg": _pf(prediction.home_last5_goals_against_avg),
            },
            "away_last5": {
                "form": _pf(prediction.away_last5_form),
                "att":  _pf(prediction.away_last5_att),
                "def":  _pf(prediction.away_last5_def),
                "goals_for_avg":     _pf(prediction.away_last5_goals_for_avg),
                "goals_against_avg": _pf(prediction.away_last5_goals_against_avg),
            },
            # Season stats
            "home_season": {
                "form": prediction.home_season_form,
                "clean_sheet": {"home": prediction.home_clean_sheet_home, "away": prediction.home_clean_sheet_away, "total": prediction.home_clean_sheet_total},
                "failed_to_score_total": prediction.home_failed_to_score_total,
                "wins":  {"home": prediction.home_wins_home, "away": prediction.home_wins_away},
                "draws_total": prediction.home_draws_total,
                "loses_total": prediction.home_loses_total,
                "goals_for_avg":     _pf(prediction.home_goals_for_avg_total),
                "goals_against_avg": _pf(prediction.home_goals_against_avg_total),
            },
            "away_season": {
                "form": prediction.away_season_form,
                "clean_sheet": {"home": prediction.away_clean_sheet_home, "away": prediction.away_clean_sheet_away, "total": prediction.away_clean_sheet_total},
                "failed_to_score_total": prediction.away_failed_to_score_total,
                "wins":  {"home": prediction.away_wins_home, "away": prediction.away_wins_away},
                "draws_total": prediction.away_draws_total,
                "loses_total": prediction.away_loses_total,
                "goals_for_avg":     _pf(prediction.away_goals_for_avg_total),
                "goals_against_avg": _pf(prediction.away_goals_against_avg_total),
            },
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

    # H2H
    h2h_row = (await db.execute(
        select(FixtureH2H).where(FixtureH2H.fixture_id == fixture_id)
    )).scalar_one_or_none()
    if h2h_row is None and fixture.status_short in {"NS", "TBD", "PST", "1H", "HT", "2H"}:
        try:
            await compute_h2h_for_fixture(db, fixture_id)
            h2h_row = (await db.execute(
                select(FixtureH2H).where(FixtureH2H.fixture_id == fixture_id)
            )).scalar_one_or_none()
        except Exception:
            pass
    h2h_out = None
    if h2h_row:
        h2h_out = {
            "matches_total": h2h_row.h2h_matches_total,
            "home_wins": h2h_row.h2h_home_wins,
            "draws": h2h_row.h2h_draws,
            "away_wins": h2h_row.h2h_away_wins,
            "home_win_pct": float(h2h_row.h2h_home_win_pct),
            "draw_pct": float(h2h_row.h2h_draw_pct),
            "away_win_pct": float(h2h_row.h2h_away_win_pct),
            "avg_goals_home": float(h2h_row.h2h_avg_goals_home),
            "avg_goals_away": float(h2h_row.h2h_avg_goals_away),
            "avg_total_goals": float(h2h_row.h2h_avg_total_goals),
            "btts_rate": float(h2h_row.h2h_btts_rate),
            "over_25_rate": float(h2h_row.h2h_over_25_rate),
            "h2h_score": float(h2h_row.h2h_score),
            "is_low_sample": 0 < h2h_row.h2h_matches_total < H2H_MIN_MATCHES,
            "sample_note": f"Nur {h2h_row.h2h_matches_total} Direktduell(e) in der Datenbasis." if 0 < h2h_row.h2h_matches_total < H2H_MIN_MATCHES else None,
        }

    # Goal Timing
    timing_rows = (await db.execute(
        select(TeamGoalTiming).where(
            TeamGoalTiming.league_id == fixture.league_id,
            TeamGoalTiming.season_year == fixture.season_year,
            TeamGoalTiming.team_id.in_([fixture.home_team_id, fixture.away_team_id]),
            TeamGoalTiming.scope == "overall",
        )
    )).scalars().all()
    timing_map = {t.team_id: t for t in timing_rows}

    def _timing_to_dict(t: TeamGoalTiming | None) -> dict | None:
        if t is None:
            return None
        return {
            "games_played": t.games_played,
            "goals_scored": t.goals_scored,
            "timing_attack": t.timing_attack,
            "timing_defense": t.timing_defense,
            "ht_attack_ratio": float(t.ht_attack_ratio) if t.ht_attack_ratio else None,
            "profil_typ": t.profil_typ,
            "p_goal_first_30": float(t.p_goal_first_30) if t.p_goal_first_30 else None,
            "p_goal_last_15": float(t.p_goal_last_15) if t.p_goal_last_15 else None,
        }

    # Home Advantage
    hadv_rows = (await db.execute(
        select(TeamHomeAdvantage).where(
            TeamHomeAdvantage.league_id == fixture.league_id,
            TeamHomeAdvantage.season_year == fixture.season_year,
            TeamHomeAdvantage.team_id.in_([fixture.home_team_id, fixture.away_team_id]),
        )
    )).scalars().all()
    hadv_map = {h.team_id: h for h in hadv_rows}

    def _hadv_to_dict(h: TeamHomeAdvantage | None) -> dict | None:
        if h is None:
            return None
        return {
            "home_ppg": float(h.home_ppg),
            "away_ppg": float(h.away_ppg),
            "advantage_factor": float(h.advantage_factor),
            "normalized_factor": float(h.normalized_factor),
            "tier": h.tier,
            "games_home": h.games_home,
            "games_away": h.games_away,
        }

    # Scoreline + MRP + Value Bets + Pattern Evaluation (graceful fallback)
    scoreline_out = None
    mrp_out = None
    value_bets_out = None
    evaluation_out = None
    pattern_predictions_out = None
    top_scorer_pattern_out = None
    try:
        from app.models.fixture_scoreline_distribution import FixtureScorelineDistribution
        from app.models.fixture_match_result_probability import FixtureMatchResultProbability
        from app.models.fixture_value_bet import FixtureValueBet
        from app.models.fixture_pattern_evaluation import FixturePatternEvaluation

        sd_row = (await db.execute(
            select(FixtureScorelineDistribution).where(FixtureScorelineDistribution.fixture_id == fixture_id)
        )).scalar_one_or_none()
        if sd_row:
            scoreline_out = {
                "lambda_home": float(sd_row.lambda_home),
                "lambda_away": float(sd_row.lambda_away),
                "p_matrix": sd_row.p_matrix,
                "p_home_win": float(sd_row.p_home_win),
                "p_draw": float(sd_row.p_draw),
                "p_away_win": float(sd_row.p_away_win),
                "p_btts": float(sd_row.p_btts),
                "p_over_15": float(sd_row.p_over_15),
                "p_over_25": float(sd_row.p_over_25),
                "p_over_35": float(sd_row.p_over_35),
                "p_home_clean_sheet": float(sd_row.p_home_clean_sheet),
                "p_away_clean_sheet": float(sd_row.p_away_clean_sheet),
                "most_likely_score": sd_row.most_likely_score,
                "most_likely_score_prob": float(sd_row.most_likely_score_prob),
            }

        mrp_row = (await db.execute(
            select(FixtureMatchResultProbability).where(FixtureMatchResultProbability.fixture_id == fixture_id)
        )).scalar_one_or_none()
        if mrp_row:
            mrp_out = {
                "p_home_win": float(mrp_row.p_home_win),
                "p_draw": float(mrp_row.p_draw),
                "p_away_win": float(mrp_row.p_away_win),
                "p_btts": float(mrp_row.p_btts),
                "p_over_25": float(mrp_row.p_over_25),
                "p_over_15": float(mrp_row.p_over_15),
                "p_over_35": float(mrp_row.p_over_35),
                "confidence": float(mrp_row.confidence),
                "elo_home_prob": float(mrp_row.elo_home_prob) if mrp_row.elo_home_prob else None,
                "elo_away_prob": float(mrp_row.elo_away_prob) if mrp_row.elo_away_prob else None,
            }

        vb_rows = (await db.execute(
            select(FixtureValueBet)
            .where(FixtureValueBet.fixture_id == fixture_id)
            .order_by(FixtureValueBet.edge.desc())
        )).scalars().all()
        if vb_rows:
            value_bets_out = [
                {
                    "market_name": v.market_name,
                    "bet_value": v.bet_value,
                    "model_prob": float(v.model_prob),
                    "bookmaker_odd": float(v.bookmaker_odd),
                    "implied_prob": float(v.implied_prob),
                    "edge": float(v.edge),
                    "expected_value": float(v.expected_value),
                    "kelly_fraction": float(v.kelly_fraction),
                    "fair_odd": float(v.fair_odd),
                    "tier": v.tier,
                }
                for v in vb_rows
            ]
        eval_row = (await db.execute(
            select(FixturePatternEvaluation).where(FixturePatternEvaluation.fixture_id == fixture_id)
        )).scalar_one_or_none()
        if eval_row:
            evaluation_out = {
                "actual_outcome": eval_row.actual_outcome,
                "predicted_outcome": eval_row.predicted_outcome,
                "outcome_correct": eval_row.outcome_correct,
                "p_home_win": float(eval_row.p_home_win),
                "p_draw": float(eval_row.p_draw),
                "p_away_win": float(eval_row.p_away_win),
                "p_actual_outcome": float(eval_row.p_actual_outcome),
                "log_loss": float(eval_row.log_loss),
                "brier_score": float(eval_row.brier_score),
                "predicted_total_goals": float(eval_row.predicted_total_goals),
                "actual_total_goals": eval_row.actual_total_goals,
                "goals_diff": float(eval_row.goals_diff),
                "p_over_25": float(eval_row.p_over_25),
                "predicted_over_25": eval_row.predicted_over_25,
                "actual_over_25": eval_row.actual_over_25,
                "over_25_correct": eval_row.over_25_correct,
                "p_btts": float(eval_row.p_btts),
                "predicted_btts": eval_row.predicted_btts,
                "actual_btts": eval_row.actual_btts,
                "btts_correct": eval_row.btts_correct,
                "predicted_score": eval_row.predicted_score,
                "predicted_score_prob": float(eval_row.predicted_score_prob) if eval_row.predicted_score_prob else None,
                "actual_score": eval_row.actual_score,
                "score_correct": eval_row.score_correct,
                "computed_at": eval_row.computed_at.isoformat() if eval_row.computed_at else None,
            }

        ts_row = (await db.execute(
            select(FixtureTopScorerPattern).where(FixtureTopScorerPattern.fixture_id == fixture_id)
        )).scalar_one_or_none()
        if ts_row is None:
            await compute_top_scorer_for_fixture(db, fixture_id)
            ts_row = (await db.execute(
                select(FixtureTopScorerPattern).where(FixtureTopScorerPattern.fixture_id == fixture_id)
            )).scalar_one_or_none()
        if ts_row:
            top_scorer_pattern_out = {
                "top_scorer": ts_row.top_scorer,
                "home_candidates": ts_row.home_candidates,
                "away_candidates": ts_row.away_candidates,
                "home_penalties_per_match": float(ts_row.home_penalties_per_match) if ts_row.home_penalties_per_match is not None else None,
                "away_penalties_per_match": float(ts_row.away_penalties_per_match) if ts_row.away_penalties_per_match is not None else None,
                "home_penalty_conversion_share": float(ts_row.home_penalty_conversion_share) if ts_row.home_penalty_conversion_share is not None else None,
                "away_penalty_conversion_share": float(ts_row.away_penalty_conversion_share) if ts_row.away_penalty_conversion_share is not None else None,
                "model_confidence": float(ts_row.model_confidence),
                "sample_size_home": ts_row.sample_size_home,
                "sample_size_away": ts_row.sample_size_away,
                "model_version": ts_row.model_version,
                "computed_at": ts_row.computed_at.isoformat() if ts_row.computed_at else None,
            }
    except Exception:
        pass

    pattern_predictions_out = _build_pattern_predictions(
        fixture=fixture,
        mrp_out=mrp_out,
        scoreline_out=scoreline_out,
        gp_home=_gp_to_dict(gp_home),
        gp_away=_gp_to_dict(gp_away),
    )

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
        h2h=h2h_out,
        goal_timing_home=_timing_to_dict(timing_map.get(fixture.home_team_id)),
        goal_timing_away=_timing_to_dict(timing_map.get(fixture.away_team_id)),
        home_advantage_home=_hadv_to_dict(hadv_map.get(fixture.home_team_id)),
        home_advantage_away=_hadv_to_dict(hadv_map.get(fixture.away_team_id)),
        scoreline_distribution=scoreline_out,
        match_result_probability=mrp_out,
        pattern_predictions=pattern_predictions_out,
        value_bets=value_bets_out,
        pattern_evaluation=evaluation_out,
        top_scorer_pattern=top_scorer_pattern_out,
    )


@router.post("/{fixture_id}/gpt-analysis")
async def get_gpt_analysis(
    fixture_id: int,
    force: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """Gibt gecachte GPT-4o Spielanalyse zurück oder generiert eine neue."""
    from app.services.gpt_analysis_service import generate_gpt_analysis
    try:
        return await generate_gpt_analysis(db, fixture_id, force=force)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GPT-Analyse Fehler: {e}")


@router.post("/{fixture_id}/ai-picks")
async def get_ai_picks(
    fixture_id: int,
    force: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """Generiert oder lädt 5 Wett-Picks + Torschütze via Claude AI. force=true → Neuberechnung."""
    try:
        result = await generate_ai_picks(db, fixture_id, force=force)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI-Picks Fehler: {e}")


from app.models.fixture_ai_pick import FixtureAiPick as _FixtureAiPick


@router.patch("/{fixture_id}/ai-picks/results")
async def update_pick_results(
    fixture_id: int,
    results: list[dict],   # [{pick_index: 0, result: "win"}, ...]
    db: AsyncSession = Depends(get_db),
):
    """
    Setzt das Ergebnis (win/loss/push) für einzelne Picks nach Spielende.
    Body: [{"pick_index": 0, "result": "win"}, ...]
    """
    row = (await db.execute(
        select(_FixtureAiPick).where(_FixtureAiPick.fixture_id == fixture_id)
    )).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Keine AI-Picks für dieses Fixture")

    picks = list(row.picks)
    for r in results:
        idx = r.get("pick_index")
        result_val = r.get("result")
        if idx is None or result_val not in ("win", "loss", "push", None):
            raise HTTPException(status_code=400, detail=f"Ungültiger Eintrag: {r}")
        if 0 <= idx < len(picks):
            picks[idx] = {**picks[idx], "result": result_val}

    from sqlalchemy import update as sa_update
    await db.execute(
        sa_update(_FixtureAiPick)
        .where(_FixtureAiPick.fixture_id == fixture_id)
        .values(picks=picks, updated_at=datetime.utcnow())
    )
    await db.commit()
    return {"fixture_id": fixture_id, "picks": picks}


@router.get("/evaluations")
async def list_evaluations(
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    season_year: int = Query(2025),
    league_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Liste aller Pattern-Evaluierungen mit Fixture-Basisdaten.
    Standard: letzte 7 Tage. Sortierung: neueste zuerst.
    """
    from app.models.fixture_pattern_evaluation import FixturePatternEvaluation as _FPE
    from datetime import timedelta

    today = date.today()
    date_from = from_date or (today - timedelta(days=7))
    date_to   = to_date   or today

    # Join fixtures + league + evaluation
    stmt = (
        select(Fixture, League, _FPE)
        .join(League, League.id == Fixture.league_id)
        .join(_FPE, _FPE.fixture_id == Fixture.id)
        .options(selectinload(Fixture.home_team), selectinload(Fixture.away_team))
        .where(
            Fixture.season_year == season_year,
            cast(Fixture.kickoff_utc, Date) >= date_from,
            cast(Fixture.kickoff_utc, Date) <= date_to,
        )
    )
    if league_id:
        stmt = stmt.where(Fixture.league_id == league_id)
    stmt = stmt.order_by(Fixture.kickoff_utc.desc())

    rows = (await db.execute(stmt)).all()

    result = []
    for fixture, league, ev in rows:
        result.append({
            **_to_out(fixture, league).__dict__,
            "actual_outcome": ev.actual_outcome,
            "predicted_outcome": ev.predicted_outcome,
            "outcome_correct": ev.outcome_correct,
            "p_home_win": float(ev.p_home_win),
            "p_draw": float(ev.p_draw),
            "p_away_win": float(ev.p_away_win),
            "p_actual_outcome": float(ev.p_actual_outcome),
            "log_loss": float(ev.log_loss),
            "brier_score": float(ev.brier_score),
            "predicted_total_goals": float(ev.predicted_total_goals),
            "actual_total_goals": ev.actual_total_goals,
            "goals_diff": float(ev.goals_diff),
            "dc_prediction": ev.dc_prediction,
            "dc_prob": float(ev.dc_prob) if ev.dc_prob is not None else None,
            "dc_correct": ev.dc_correct,
            "p_over_25": float(ev.p_over_25),
            "predicted_over_25": ev.predicted_over_25,
            "actual_over_25": ev.actual_over_25,
            "over_25_correct": ev.over_25_correct,
            "p_over_15": float(ev.p_over_15) if ev.p_over_15 is not None else None,
            "over_15_correct": ev.over_15_correct,
            "p_btts": float(ev.p_btts),
            "predicted_btts": ev.predicted_btts,
            "actual_btts": ev.actual_btts,
            "btts_correct": ev.btts_correct,
            "p_home_scores": float(ev.p_home_scores) if ev.p_home_scores is not None else None,
            "home_scores_correct": ev.home_scores_correct,
            "p_away_scores": float(ev.p_away_scores) if ev.p_away_scores is not None else None,
            "away_scores_correct": ev.away_scores_correct,
            "predicted_score": ev.predicted_score,
            "predicted_score_prob": float(ev.predicted_score_prob) if ev.predicted_score_prob else None,
            "actual_score": ev.actual_score,
            "score_correct": ev.score_correct,
            "computed_at": ev.computed_at.isoformat() if ev.computed_at else None,
        })
    return result


@router.get("/today/enriched")
async def fixtures_today_enriched(
    for_date: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Heutige Fixtures mit KI-Pick-Status, MRP und Torwahrscheinlichkeiten."""
    from sqlalchemy import text
    target = for_date or date.today()

    # Load fixtures
    stmt = (
        select(Fixture, League)
        .join(League, League.id == Fixture.league_id)
        .options(selectinload(Fixture.home_team), selectinload(Fixture.away_team))
        .where(cast(Fixture.kickoff_utc, Date) == target)
        .order_by(Fixture.kickoff_utc)
    )
    rows = (await db.execute(stmt)).all()
    if not rows:
        return []

    fixture_ids = [f.id for f, _ in rows]

    # AI picks existence check
    from app.models.fixture_ai_pick import FixtureAiPick as _FxPick
    picks_rows = (await db.execute(
        select(_FxPick.fixture_id).where(_FxPick.fixture_id.in_(fixture_ids))
    )).scalars().all()
    has_picks = set(picks_rows)

    # MRP
    try:
        from app.models.fixture_match_result_probability import FixtureMatchResultProbability as _MRP
        mrp_rows = (await db.execute(
            select(_MRP).where(_MRP.fixture_id.in_(fixture_ids))
        )).scalars().all()
        mrp_by_id = {r.fixture_id: r for r in mrp_rows}
    except Exception:
        mrp_by_id = {}

    # Goal probability (p_ge_1_goal per team)
    gp_rows = (await db.execute(
        select(FixtureGoalProbability).where(
            FixtureGoalProbability.fixture_id.in_(fixture_ids)
        )
    )).scalars().all()
    gp_by_fixture: dict[int, dict] = {}
    for gp in gp_rows:
        gp_by_fixture.setdefault(gp.fixture_id, {})[gp.team_id] = gp

    # Pattern evaluation (only for finished fixtures)
    finished_ids = [
        f.id for f, _ in rows
        if f.status_short in {"FT", "AET", "PEN"}
    ]
    eval_by_id: dict[int, object] = {}
    if finished_ids:
        try:
            from app.models.fixture_pattern_evaluation import FixturePatternEvaluation as _FPE
            eval_rows = (await db.execute(
                select(_FPE).where(_FPE.fixture_id.in_(finished_ids))
            )).scalars().all()
            eval_by_id = {r.fixture_id: r for r in eval_rows}
        except Exception:
            pass

    result = []
    for fixture, league in rows:
        base = _to_out(fixture, league).__dict__
        mrp = mrp_by_id.get(fixture.id)
        gps = gp_by_fixture.get(fixture.id, {})
        gp_home = gps.get(fixture.home_team_id)
        gp_away = gps.get(fixture.away_team_id)
        ev = eval_by_id.get(fixture.id)
        evaluation = None
        if ev is not None:
            evaluation = {
                "outcome_correct": ev.outcome_correct,
                "predicted_outcome": ev.predicted_outcome,
                "actual_outcome": ev.actual_outcome,
                "p_actual_outcome": float(ev.p_actual_outcome),
                "dc_prediction": ev.dc_prediction,
                "dc_correct": ev.dc_correct,
                "over_25_correct": ev.over_25_correct,
                "over_15_correct": ev.over_15_correct,
                "btts_correct": ev.btts_correct,
                "home_scores_correct": ev.home_scores_correct,
                "away_scores_correct": ev.away_scores_correct,
                "score_correct": ev.score_correct,
                "predicted_score": ev.predicted_score,
                "actual_score": ev.actual_score,
                "brier_score": float(ev.brier_score),
                "goals_diff": float(ev.goals_diff),
            }
        result.append({
            **base,
            "has_ai_picks": fixture.id in has_picks,
            "p_home_win":   float(mrp.p_home_win)  if mrp else None,
            "p_draw":       float(mrp.p_draw)       if mrp else None,
            "p_away_win":   float(mrp.p_away_win)   if mrp else None,
            "p_btts":       float(mrp.p_btts)       if mrp else None,
            "p_over_15":    float(mrp.p_over_15)    if mrp and mrp.p_over_15 is not None else None,
            "p_goal_home":  float(gp_home.p_ge_1_goal) if gp_home else None,
            "p_goal_away":  float(gp_away.p_ge_1_goal) if gp_away else None,
            "evaluation":   evaluation,
        })
    return result


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
