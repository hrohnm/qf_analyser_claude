from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fixture import Fixture
from app.models.fixture_statistics import FixtureStatistics
from app.models.team_elo_snapshot import TeamEloSnapshot
from app.models.team_form_snapshot import TeamFormSnapshot
from app.services.team_elo_service import recompute_team_elo_for_league

FINISHED_STATUSES = {"FT", "AET", "PEN"}
MODEL_VERSION = "team_form_v1"
SCOPES = ("overall", "home", "away")


@dataclass
class _Metrics:
    form_score: float
    result_score: float
    performance_score: float
    trend_score: float
    opponent_strength_score: float
    elo_adjusted_result_score: float
    form_trend: str
    form_bucket: str
    games_considered: int


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _norm(value: float) -> float:
    return (value + 1.0) / 2.0


def _trend_label(delta: float) -> str:
    if delta > 0.35:
        return "up"
    if delta < -0.35:
        return "down"
    return "flat"


def _bucket(score: float) -> str:
    if score < 40:
        return "schwach"
    if score < 70:
        return "mittel"
    return "stark"


def _points(gf: int, ga: int) -> int:
    if gf > ga:
        return 3
    if gf == ga:
        return 1
    return 0


def _compute_metrics(
    team_id: int,
    fixtures_desc: list[Fixture],
    stats_map: dict[tuple[int, int], FixtureStatistics],
    elo_by_team: dict[int, TeamEloSnapshot],
    league_elo_mean: float,
    window_size: int,
) -> _Metrics | None:
    considered = fixtures_desc[:window_size]
    games = len(considered)
    if games == 0:
        return None

    weighted_points_sum = 0.0
    weight_sum = 0.0
    points_seq: list[int] = []
    goals_for = goals_against = 0
    xg_for = xg_against = 0.0
    shots_on_target_for = shots_on_target_against = 0
    opp_elo_values: list[float] = []

    for f in considered:
        is_home = f.home_team_id == team_id
        opp_id = f.away_team_id if is_home else f.home_team_id
        gf = f.home_score if is_home else f.away_score
        ga = f.away_score if is_home else f.home_score
        if gf is None or ga is None:
            continue

        p = _points(gf, ga)
        points_seq.append(p)
        goals_for += gf
        goals_against += ga

        opp_elo = float(elo_by_team.get(opp_id).elo_overall) if opp_id in elo_by_team else league_elo_mean
        opp_elo_values.append(opp_elo)
        weight = _clamp(opp_elo / league_elo_mean, 0.85, 1.15)
        weighted_points_sum += p * weight
        weight_sum += weight

        own_stats = stats_map.get((f.id, team_id))
        opp_stats = stats_map.get((f.id, opp_id))
        if own_stats and own_stats.expected_goals is not None:
            xg_for += float(own_stats.expected_goals)
        if opp_stats and opp_stats.expected_goals is not None:
            xg_against += float(opp_stats.expected_goals)
        if own_stats and own_stats.shots_on_goal is not None:
            shots_on_target_for += own_stats.shots_on_goal
        if opp_stats and opp_stats.shots_on_goal is not None:
            shots_on_target_against += opp_stats.shots_on_goal

    if not points_seq:
        return None

    games = len(points_seq)
    elo_adjusted_result = weighted_points_sum / max(0.0001, (3.0 * weight_sum))

    goal_balance = _clamp((goals_for - goals_against) / max(1.0, games * 2.0), -1.0, 1.0)
    xg_balance = _clamp((xg_for - xg_against) / max(1.0, games * 1.5), -1.0, 1.0)
    shot_quality = _clamp((shots_on_target_for - shots_on_target_against) / max(1.0, games * 4.0), -1.0, 1.0)
    performance = (0.45 * _norm(goal_balance)) + (0.35 * _norm(xg_balance)) + (0.20 * _norm(shot_quality))

    recent = points_seq[:3]
    previous = points_seq[3:6]
    recent_ppg = (sum(recent) / len(recent)) if recent else 0.0
    previous_ppg = (sum(previous) / len(previous)) if previous else recent_ppg
    delta = recent_ppg - previous_ppg
    trend = _clamp((delta + 3.0) / 6.0, 0.0, 1.0)

    avg_opp_elo = (sum(opp_elo_values) / len(opp_elo_values)) if opp_elo_values else league_elo_mean
    opponent_strength = _clamp((avg_opp_elo - (league_elo_mean - 150.0)) / 300.0, 0.0, 1.0)

    form_score = 100.0 * (
        (0.40 * elo_adjusted_result)
        + (0.35 * performance)
        + (0.15 * trend)
        + (0.10 * opponent_strength)
    )
    form_score = _clamp(form_score, 0.0, 100.0)

    return _Metrics(
        form_score=round(form_score, 2),
        result_score=round(elo_adjusted_result, 4),
        performance_score=round(performance, 4),
        trend_score=round(trend, 4),
        opponent_strength_score=round(opponent_strength, 4),
        elo_adjusted_result_score=round(elo_adjusted_result, 4),
        form_trend=_trend_label(delta),
        form_bucket=_bucket(form_score),
        games_considered=games,
    )


async def recompute_team_form_for_league(
    db: AsyncSession,
    league_id: int,
    season_year: int,
    window_size: int = 5,
    extra_league_ids: list[int] | None = None,
) -> dict:
    all_league_ids = [league_id] + (extra_league_ids or [])
    fixtures_result = await db.execute(
        select(Fixture)
        .where(
            Fixture.league_id.in_(all_league_ids),
            Fixture.season_year == season_year,
            Fixture.status_short.in_(FINISHED_STATUSES),
        )
        .order_by(Fixture.kickoff_utc.desc(), Fixture.id.desc())
    )
    fixtures = fixtures_result.scalars().all()
    if not fixtures:
        await db.execute(
            TeamFormSnapshot.__table__.delete().where(
                TeamFormSnapshot.league_id == league_id,
                TeamFormSnapshot.season_year == season_year,
                TeamFormSnapshot.window_size == window_size,
            )
        )
        await db.commit()
        return {"league_id": league_id, "season_year": season_year, "window_size": window_size, "rows": 0}

    team_ids: set[int] = set()
    fixture_ids: list[int] = []
    fixtures_by_team: dict[int, dict[str, list[Fixture]]] = {}
    for f in fixtures:
        if f.home_score is None or f.away_score is None:
            continue
        team_ids.add(f.home_team_id)
        team_ids.add(f.away_team_id)
        fixture_ids.append(f.id)
        for tid in (f.home_team_id, f.away_team_id):
            fixtures_by_team.setdefault(tid, {"overall": [], "home": [], "away": []})
        fixtures_by_team[f.home_team_id]["overall"].append(f)
        fixtures_by_team[f.home_team_id]["home"].append(f)
        fixtures_by_team[f.away_team_id]["overall"].append(f)
        fixtures_by_team[f.away_team_id]["away"].append(f)

    elo_result = await db.execute(
        select(TeamEloSnapshot).where(
            TeamEloSnapshot.league_id == league_id,
            TeamEloSnapshot.season_year == season_year,
        )
    )
    elo_rows = elo_result.scalars().all()
    if not elo_rows:
        await recompute_team_elo_for_league(
            db, league_id=league_id, season_year=season_year,
            extra_league_ids=extra_league_ids,
        )
        elo_result = await db.execute(
            select(TeamEloSnapshot).where(
                TeamEloSnapshot.league_id == league_id,
                TeamEloSnapshot.season_year == season_year,
            )
        )
        elo_rows = elo_result.scalars().all()
    elo_by_team = {r.team_id: r for r in elo_rows}
    league_elo_mean = (
        sum(float(r.elo_overall) for r in elo_rows) / len(elo_rows)
        if elo_rows else 1500.0
    )

    stats_result = await db.execute(
        select(FixtureStatistics).where(FixtureStatistics.fixture_id.in_(fixture_ids))
    )
    stats_map = {(s.fixture_id, s.team_id): s for s in stats_result.scalars().all()}

    await db.execute(
        TeamFormSnapshot.__table__.delete().where(
            TeamFormSnapshot.league_id == league_id,
            TeamFormSnapshot.season_year == season_year,
            TeamFormSnapshot.window_size == window_size,
        )
    )

    now = datetime.utcnow()
    rows_written = 0
    for team_id in team_ids:
        scoped = fixtures_by_team.get(team_id, {"overall": [], "home": [], "away": []})
        for scope in SCOPES:
            metrics = _compute_metrics(
                team_id=team_id,
                fixtures_desc=scoped.get(scope, []),
                stats_map=stats_map,
                elo_by_team=elo_by_team,
                league_elo_mean=league_elo_mean,
                window_size=window_size,
            )
            if metrics is None:
                continue
            db.add(
                TeamFormSnapshot(
                    team_id=team_id,
                    league_id=league_id,
                    season_year=season_year,
                    window_size=window_size,
                    scope=scope,
                    form_score=metrics.form_score,
                    result_score=metrics.result_score,
                    performance_score=metrics.performance_score,
                    trend_score=metrics.trend_score,
                    opponent_strength_score=metrics.opponent_strength_score,
                    elo_adjusted_result_score=metrics.elo_adjusted_result_score,
                    form_trend=metrics.form_trend,
                    form_bucket=metrics.form_bucket,
                    games_considered=metrics.games_considered,
                    computed_at=now,
                    model_version=MODEL_VERSION,
                )
            )
            rows_written += 1

    await db.commit()
    return {
        "league_id": league_id,
        "season_year": season_year,
        "window_size": window_size,
        "rows": rows_written,
    }
