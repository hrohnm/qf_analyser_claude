from __future__ import annotations

import math
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fixture import Fixture
from app.models.fixture_goal_probability import FixtureGoalProbability
from app.models.team_elo_snapshot import TeamEloSnapshot

FINISHED_STATUSES = {"FT", "AET", "PEN"}
MODEL_VERSION = "goal_prob_v2"
RECENCY_ALPHA = 0.02
WINDOW = 12
SEASONS_LOOKBACK = 5


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _poisson_tail(lmbd: float, at_least: int) -> float:
    if lmbd < 0:
        return 0.0
    if at_least <= 0:
        return 1.0
    # 1 - sum_{k=0}^{n-1} P(k)
    s = 0.0
    for k in range(at_least):
        s += math.exp(-lmbd) * (lmbd ** k) / math.factorial(k)
    return _clamp(1.0 - s, 0.0, 1.0)


async def _recent_team_matches(
    db: AsyncSession,
    team_id: int,
    league_id: int,
    season_year: int,
    before_kickoff: datetime | None,
    limit: int = WINDOW,
) -> list[Fixture]:
    stmt = (
        select(Fixture)
        .where(
            Fixture.league_id == league_id,
            Fixture.season_year >= season_year - (SEASONS_LOOKBACK - 1),
            Fixture.season_year <= season_year,
            Fixture.status_short.in_(FINISHED_STATUSES),
            (Fixture.home_team_id == team_id) | (Fixture.away_team_id == team_id),
        )
        .order_by(Fixture.kickoff_utc.desc(), Fixture.id.desc())
        .limit(limit)
    )
    if before_kickoff is not None:
        stmt = stmt.where(Fixture.kickoff_utc < before_kickoff)
    rows = await db.execute(stmt)
    return rows.scalars().all()


async def _league_avg_goals_against(
    db: AsyncSession,
    league_id: int,
    season_year: int,
    before_kickoff: datetime | None,
) -> float:
    stmt = (
        select(Fixture)
        .where(
            Fixture.league_id == league_id,
            Fixture.season_year >= season_year - (SEASONS_LOOKBACK - 1),
            Fixture.season_year <= season_year,
            Fixture.status_short.in_(FINISHED_STATUSES),
        )
    )
    if before_kickoff is not None:
        stmt = stmt.where(Fixture.kickoff_utc < before_kickoff)
    rows = await db.execute(stmt)
    fixtures = rows.scalars().all()
    if not fixtures:
        return 1.4
    total_goals = 0
    team_games = 0
    for f in fixtures:
        if f.home_score is None or f.away_score is None:
            continue
        total_goals += f.home_score + f.away_score
        team_games += 2
    if team_games == 0:
        return 1.4
    return max(0.2, total_goals / team_games)


async def _opponent_avg_goals_against(
    db: AsyncSession,
    opponent_id: int,
    league_id: int,
    season_year: int,
    before_kickoff: datetime | None,
    cache: dict[int, float],
) -> float:
    if opponent_id in cache:
        return cache[opponent_id]

    fixtures = await _recent_team_matches(
        db=db,
        team_id=opponent_id,
        league_id=league_id,
        season_year=season_year,
        before_kickoff=before_kickoff,
        limit=20,
    )
    ga_total = 0
    games = 0
    for f in fixtures:
        if f.home_score is None or f.away_score is None:
            continue
        if f.home_team_id == opponent_id:
            ga_total += f.away_score
        else:
            ga_total += f.home_score
        games += 1
    value = (ga_total / games) if games > 0 else 1.4
    cache[opponent_id] = value
    return value


async def _compute_for_team(
    db: AsyncSession,
    fixture: Fixture,
    team_id: int,
    is_home_target: bool,
    elo_by_team: dict[int, TeamEloSnapshot],
    league_elo_mean: float,
    league_avg_ga: float,
    opp_ga_cache: dict[int, float],
) -> dict:
    matches = await _recent_team_matches(
        db=db,
        team_id=team_id,
        league_id=fixture.league_id,
        season_year=fixture.season_year,
        before_kickoff=fixture.kickoff_utc,
        limit=WINDOW,
    )
    if not matches:
        return {
            "lambda_weighted": 0.9,
            "p_ge_1_goal": _poisson_tail(0.9, 1),
            "p_ge_2_goals": _poisson_tail(0.9, 2),
            "p_ge_3_goals": _poisson_tail(0.9, 3),
            "confidence": 0.2,
            "sample_size": 0,
        }

    weighted_goals = 0.0
    weighted_games = 0.0
    matches_used = 0

    for m in matches:
        if m.home_score is None or m.away_score is None:
            continue
        matches_used += 1
        hist_is_home = (m.home_team_id == team_id)
        goals_for = m.home_score if hist_is_home else m.away_score
        opp_id = m.away_team_id if hist_is_home else m.home_team_id

        opp_elo = float(elo_by_team[opp_id].elo_overall) if opp_id in elo_by_team else league_elo_mean
        w_elo = _clamp(opp_elo / league_elo_mean, 0.85, 1.20)

        opp_avg_ga = await _opponent_avg_goals_against(
            db=db,
            opponent_id=opp_id,
            league_id=fixture.league_id,
            season_year=fixture.season_year,
            before_kickoff=fixture.kickoff_utc,
            cache=opp_ga_cache,
        )
        w_def = _clamp(league_avg_ga / max(0.2, opp_avg_ga), 0.80, 1.25)

        w_venue = 1.10 if hist_is_home == is_home_target else 0.90

        if m.kickoff_utc and fixture.kickoff_utc:
            days = max(0.0, (fixture.kickoff_utc - m.kickoff_utc).total_seconds() / 86400.0)
        else:
            days = 30.0
        w_recency = math.exp(-RECENCY_ALPHA * days)

        w = w_elo * w_def * w_venue * w_recency
        weighted_goals += goals_for * w
        weighted_games += w

    if weighted_games <= 0:
        lmbd = 0.9
    else:
        lmbd = _clamp(weighted_goals / weighted_games, 0.05, 4.5)

    confidence = _clamp(weighted_games / 8.0, 0.2, 1.0)
    return {
        "lambda_weighted": round(lmbd, 4),
        "p_ge_1_goal": round(_poisson_tail(lmbd, 1), 4),
        "p_ge_2_goals": round(_poisson_tail(lmbd, 2), 4),
        "p_ge_3_goals": round(_poisson_tail(lmbd, 3), 4),
        "confidence": round(confidence, 4),
        "sample_size": matches_used,
    }


async def recompute_goal_probability_for_fixture(db: AsyncSession, fixture_id: int) -> dict:
    fixture = await db.get(Fixture, fixture_id)
    if fixture is None:
        return {"fixture_id": fixture_id, "rows": 0}

    elo_rows = await db.execute(
        select(TeamEloSnapshot).where(
            TeamEloSnapshot.league_id == fixture.league_id,
            TeamEloSnapshot.season_year == fixture.season_year,
        )
    )
    elo_list = elo_rows.scalars().all()
    elo_by_team = {r.team_id: r for r in elo_list}
    league_elo_mean = (
        sum(float(r.elo_overall) for r in elo_list) / len(elo_list)
        if elo_list else 1500.0
    )
    league_avg_ga = await _league_avg_goals_against(
        db=db,
        league_id=fixture.league_id,
        season_year=fixture.season_year,
        before_kickoff=fixture.kickoff_utc,
    )
    opp_ga_cache: dict[int, float] = {}

    home = await _compute_for_team(
        db=db,
        fixture=fixture,
        team_id=fixture.home_team_id,
        is_home_target=True,
        elo_by_team=elo_by_team,
        league_elo_mean=league_elo_mean,
        league_avg_ga=league_avg_ga,
        opp_ga_cache=opp_ga_cache,
    )
    away = await _compute_for_team(
        db=db,
        fixture=fixture,
        team_id=fixture.away_team_id,
        is_home_target=False,
        elo_by_team=elo_by_team,
        league_elo_mean=league_elo_mean,
        league_avg_ga=league_avg_ga,
        opp_ga_cache=opp_ga_cache,
    )

    # p_btts = p(home scores >= 1) * p(away scores >= 1) * 0.95 (5% correlation discount)
    p_btts = round(_clamp(home["p_ge_1_goal"] * away["p_ge_1_goal"] * 0.95, 0.0, 1.0), 4)

    now = datetime.utcnow()
    for team_id, is_home, payload in (
        (fixture.home_team_id, True, home),
        (fixture.away_team_id, False, away),
    ):
        stmt = pg_insert(FixtureGoalProbability).values(
            fixture_id=fixture.id,
            team_id=team_id,
            is_home=is_home,
            season_year=fixture.season_year,
            league_id=fixture.league_id,
            lambda_weighted=payload["lambda_weighted"],
            p_ge_1_goal=payload["p_ge_1_goal"],
            p_ge_2_goals=payload["p_ge_2_goals"],
            p_ge_3_goals=payload["p_ge_3_goals"],
            confidence=payload["confidence"],
            sample_size=payload["sample_size"],
            p_btts=p_btts,
            computed_at=now,
            model_version=MODEL_VERSION,
        ).on_conflict_do_update(
            constraint="uq_fixture_goal_probability",
            set_={
                "is_home": is_home,
                "season_year": fixture.season_year,
                "league_id": fixture.league_id,
                "lambda_weighted": payload["lambda_weighted"],
                "p_ge_1_goal": payload["p_ge_1_goal"],
                "p_ge_2_goals": payload["p_ge_2_goals"],
                "p_ge_3_goals": payload["p_ge_3_goals"],
                "confidence": payload["confidence"],
                "sample_size": payload["sample_size"],
                "p_btts": p_btts,
                "computed_at": now,
                "model_version": MODEL_VERSION,
            },
        )
        await db.execute(stmt)

    await db.commit()
    return {"fixture_id": fixture.id, "rows": 2}
