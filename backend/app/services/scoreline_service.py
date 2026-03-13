from __future__ import annotations

import math
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fixture import Fixture
from app.models.fixture_goal_probability import FixtureGoalProbability
from app.models.fixture_scoreline_distribution import FixtureScorelineDistribution

MODEL_VERSION = "scoreline_v2"
FALLBACK_LAMBDA_HOME = 1.4
FALLBACK_LAMBDA_AWAY = 1.2
SCORE_RANGE = 6  # 0..5 for computing, but only 0..4 stored in p_matrix

# Calibration factor: historical lambdas systematically underestimate actual goals
# (avg predicted 2.60 vs actual 2.74 → factor 2.74/2.60 = 1.055)
LAMBDA_CALIBRATION = 1.055


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _poisson_pmf(lmbd: float, k: int) -> float:
    if lmbd <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lmbd) * (lmbd ** k) / math.factorial(k)


def _compute_matrix(lambda_home: float, lambda_away: float) -> dict[tuple[int, int], float]:
    """Compute P(i,j) for i,j in 0..SCORE_RANGE-1 via independent Poisson."""
    matrix: dict[tuple[int, int], float] = {}
    total = 0.0
    for i in range(SCORE_RANGE):
        for j in range(SCORE_RANGE):
            p = _poisson_pmf(lambda_home, i) * _poisson_pmf(lambda_away, j)
            matrix[(i, j)] = p
            total += p

    # Normalise so probabilities sum to 1.0
    if total > 0:
        matrix = {k: v / total for k, v in matrix.items()}
    return matrix


def _derive_market_probs(matrix: dict[tuple[int, int], float]) -> dict:
    p_home_win = sum(v for (i, j), v in matrix.items() if i > j)
    p_draw = sum(v for (i, j), v in matrix.items() if i == j)
    p_away_win = sum(v for (i, j), v in matrix.items() if j > i)
    p_btts = sum(v for (i, j), v in matrix.items() if i > 0 and j > 0)
    p_over_15 = sum(v for (i, j), v in matrix.items() if i + j > 1)
    p_over_25 = sum(v for (i, j), v in matrix.items() if i + j > 2)
    p_over_35 = sum(v for (i, j), v in matrix.items() if i + j > 3)
    p_home_clean_sheet = sum(v for (i, j), v in matrix.items() if j == 0)
    p_away_clean_sheet = sum(v for (i, j), v in matrix.items() if i == 0)
    return {
        "p_home_win": round(_clamp(p_home_win, 0.0, 1.0), 4),
        "p_draw": round(_clamp(p_draw, 0.0, 1.0), 4),
        "p_away_win": round(_clamp(p_away_win, 0.0, 1.0), 4),
        "p_btts": round(_clamp(p_btts, 0.0, 1.0), 4),
        "p_over_15": round(_clamp(p_over_15, 0.0, 1.0), 4),
        "p_over_25": round(_clamp(p_over_25, 0.0, 1.0), 4),
        "p_over_35": round(_clamp(p_over_35, 0.0, 1.0), 4),
        "p_home_clean_sheet": round(_clamp(p_home_clean_sheet, 0.0, 1.0), 4),
        "p_away_clean_sheet": round(_clamp(p_away_clean_sheet, 0.0, 1.0), 4),
    }


def _build_p_matrix_json(matrix: dict[tuple[int, int], float]) -> tuple[dict, str, float]:
    """Return (p_matrix_json, most_likely_score, most_likely_score_prob) for scores 0-0 to 4-4."""
    p_matrix: dict[str, float] = {}
    best_score = "1-1"
    best_prob = 0.0
    for i in range(5):
        for j in range(5):
            key = f"{i}_{j}"
            prob = round(matrix.get((i, j), 0.0), 4)
            p_matrix[key] = prob
            if prob > best_prob:
                best_prob = prob
                best_score = f"{i}-{j}"
    return p_matrix, best_score, round(best_prob, 4)


async def _get_lambdas(db: AsyncSession, fixture_id: int) -> tuple[float, float]:
    """Read lambda_home and lambda_away from fixture_goal_probability. Fallback if missing."""
    rows = await db.execute(
        select(FixtureGoalProbability).where(FixtureGoalProbability.fixture_id == fixture_id)
    )
    goal_probs = rows.scalars().all()

    lambda_home = FALLBACK_LAMBDA_HOME
    lambda_away = FALLBACK_LAMBDA_AWAY

    for gp in goal_probs:
        if gp.is_home:
            lambda_home = float(gp.lambda_weighted)
        else:
            lambda_away = float(gp.lambda_weighted)

    return lambda_home, lambda_away


async def compute_scoreline_for_fixture(db: AsyncSession, fixture_id: int) -> dict:
    """Compute and upsert scoreline distribution for a single fixture."""
    fixture = await db.get(Fixture, fixture_id)
    if fixture is None:
        return {"fixture_id": fixture_id, "rows": 0, "error": "fixture not found"}

    lambda_home, lambda_away = await _get_lambdas(db, fixture_id)
    lambda_home = _clamp(lambda_home * LAMBDA_CALIBRATION, 0.05, 4.5)
    lambda_away = _clamp(lambda_away * LAMBDA_CALIBRATION, 0.05, 4.5)

    matrix = _compute_matrix(lambda_home, lambda_away)
    market_probs = _derive_market_probs(matrix)
    p_matrix_json, most_likely_score, most_likely_score_prob = _build_p_matrix_json(matrix)

    now = datetime.utcnow()
    values = dict(
        fixture_id=fixture_id,
        lambda_home=round(lambda_home, 4),
        lambda_away=round(lambda_away, 4),
        p_matrix=p_matrix_json,
        most_likely_score=most_likely_score,
        most_likely_score_prob=most_likely_score_prob,
        computed_at=now,
        model_version=MODEL_VERSION,
        **market_probs,
    )

    stmt = pg_insert(FixtureScorelineDistribution).values(**values).on_conflict_do_update(
        constraint="uq_fixture_scoreline_distribution",
        set_={k: v for k, v in values.items() if k != "fixture_id"},
    )
    await db.execute(stmt)
    await db.commit()

    return {"fixture_id": fixture_id, "rows": 1, "most_likely_score": most_likely_score}


async def compute_scoreline_for_league(db: AsyncSession, league_id: int, season_year: int) -> dict:
    """Compute and upsert scoreline distributions for all fixtures in a league/season."""
    result = await db.execute(
        select(Fixture).where(
            Fixture.league_id == league_id,
            Fixture.season_year == season_year,
        )
    )
    fixtures = result.scalars().all()

    if not fixtures:
        return {"league_id": league_id, "season_year": season_year, "computed": 0}

    computed = 0
    for fixture in fixtures:
        lambda_home, lambda_away = await _get_lambdas(db, fixture.id)
        lambda_home = _clamp(lambda_home * LAMBDA_CALIBRATION, 0.05, 4.5)
        lambda_away = _clamp(lambda_away * LAMBDA_CALIBRATION, 0.05, 4.5)

        matrix = _compute_matrix(lambda_home, lambda_away)
        market_probs = _derive_market_probs(matrix)
        p_matrix_json, most_likely_score, most_likely_score_prob = _build_p_matrix_json(matrix)

        now = datetime.utcnow()
        values = dict(
            fixture_id=fixture.id,
            lambda_home=round(lambda_home, 4),
            lambda_away=round(lambda_away, 4),
            p_matrix=p_matrix_json,
            most_likely_score=most_likely_score,
            most_likely_score_prob=most_likely_score_prob,
            computed_at=now,
            model_version=MODEL_VERSION,
            **market_probs,
        )

        stmt = pg_insert(FixtureScorelineDistribution).values(**values).on_conflict_do_update(
            constraint="uq_fixture_scoreline_distribution",
            set_={k: v for k, v in values.items() if k != "fixture_id"},
        )
        await db.execute(stmt)
        computed += 1

    await db.commit()
    return {"league_id": league_id, "season_year": season_year, "computed": computed}
