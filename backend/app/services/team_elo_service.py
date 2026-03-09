from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import pow

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fixture import Fixture
from app.models.team_elo_snapshot import TeamEloSnapshot

FINISHED_STATUSES = {"FT", "AET", "PEN"}
BASE_ELO = 1500.0
HOME_ADVANTAGE = 60.0
K_FACTOR = 24.0
MODEL_VERSION = "team_elo_v1"


@dataclass
class _EloState:
    overall: float = BASE_ELO
    home: float = BASE_ELO
    away: float = BASE_ELO
    games_played: int = 0
    games_home: int = 0
    games_away: int = 0
    overall_history: list[float] | None = None

    def __post_init__(self) -> None:
        if self.overall_history is None:
            self.overall_history = [BASE_ELO]


def _expected(own_elo: float, opp_elo: float, own_is_home: bool) -> float:
    own_adj = own_elo + (HOME_ADVANTAGE if own_is_home else 0.0)
    return 1.0 / (1.0 + pow(10.0, (opp_elo - own_adj) / 400.0))


def _actual(gf: int, ga: int) -> float:
    if gf > ga:
        return 1.0
    if gf == ga:
        return 0.5
    return 0.0


def _goal_diff_factor(gf: int, ga: int) -> float:
    gd = abs(gf - ga)
    if gd <= 1:
        return 1.0
    if gd == 2:
        return 1.5
    if gd == 3:
        return 1.75
    return 2.0


def _tier(elo: float) -> str:
    if elo >= 1650.0:
        return "elite"
    if elo >= 1550.0:
        return "strong"
    if elo >= 1450.0:
        return "average"
    return "weak"


def _delta_last_5(history: list[float]) -> float:
    # history contains initial 1500 + every post-match elo value
    if len(history) <= 6:
        return round(history[-1] - history[0], 2)
    return round(history[-1] - history[-6], 2)


async def recompute_team_elo_for_league(
    db: AsyncSession,
    league_id: int,
    season_year: int,
) -> dict:
    fixtures_result = await db.execute(
        select(Fixture)
        .where(
            Fixture.league_id == league_id,
            Fixture.season_year == season_year,
            Fixture.status_short.in_(FINISHED_STATUSES),
        )
        .order_by(Fixture.kickoff_utc, Fixture.id)
    )
    fixtures = fixtures_result.scalars().all()

    if not fixtures:
        await db.execute(
            TeamEloSnapshot.__table__.delete().where(
                TeamEloSnapshot.league_id == league_id,
                TeamEloSnapshot.season_year == season_year,
            )
        )
        await db.commit()
        return {"league_id": league_id, "season_year": season_year, "teams": 0, "matches": 0}

    team_ids: set[int] = set()
    for f in fixtures:
        team_ids.add(f.home_team_id)
        team_ids.add(f.away_team_id)

    states = {tid: _EloState() for tid in team_ids}

    for f in fixtures:
        if f.home_score is None or f.away_score is None:
            continue

        home_state = states[f.home_team_id]
        away_state = states[f.away_team_id]

        expected_home = _expected(home_state.overall, away_state.overall, own_is_home=True)
        actual_home = _actual(f.home_score, f.away_score)
        gd_factor = _goal_diff_factor(f.home_score, f.away_score)
        delta = K_FACTOR * gd_factor * (actual_home - expected_home)

        home_state.overall += delta
        away_state.overall -= delta
        home_state.games_played += 1
        away_state.games_played += 1

        expected_home_split = _expected(home_state.home, away_state.away, own_is_home=True)
        delta_split = K_FACTOR * gd_factor * (actual_home - expected_home_split)
        home_state.home += delta_split
        away_state.away -= delta_split
        home_state.games_home += 1
        away_state.games_away += 1

        home_state.overall_history.append(home_state.overall)
        away_state.overall_history.append(away_state.overall)

    await db.execute(
        TeamEloSnapshot.__table__.delete().where(
            TeamEloSnapshot.league_id == league_id,
            TeamEloSnapshot.season_year == season_year,
        )
    )

    now = datetime.utcnow()
    for team_id, state in states.items():
        db.add(
            TeamEloSnapshot(
                team_id=team_id,
                league_id=league_id,
                season_year=season_year,
                elo_overall=round(state.overall, 2),
                elo_home=round(state.home, 2),
                elo_away=round(state.away, 2),
                games_played=state.games_played,
                games_home=state.games_home,
                games_away=state.games_away,
                elo_delta_last_5=_delta_last_5(state.overall_history or [BASE_ELO]),
                strength_tier=_tier(state.overall),
                computed_at=now,
                model_version=MODEL_VERSION,
            )
        )

    await db.commit()
    return {
        "league_id": league_id,
        "season_year": season_year,
        "teams": len(states),
        "matches": len(fixtures),
    }
