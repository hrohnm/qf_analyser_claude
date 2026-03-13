"""
Post-match pattern evaluation service.

For each finished fixture with MRP and ScorelineDistribution data,
computes how accurate the pre-match predictions were:
  - 1X2: predicted outcome vs. actual, probability assigned, log-loss, Brier
  - Goals: predicted lambda sum vs. actual total
  - Over/Under 2.5: correct prediction?
  - BTTS: correct prediction?
  - Score: most-likely-score vs. actual
"""
from __future__ import annotations

import asyncio
import logging
import math
from datetime import datetime, date

from sqlalchemy import cast, Date, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.fixture import Fixture
from app.models.fixture_goal_probability import FixtureGoalProbability
from app.models.fixture_match_result_probability import FixtureMatchResultProbability
from app.models.fixture_scoreline_distribution import FixtureScorelineDistribution
from app.models.fixture_pattern_evaluation import FixturePatternEvaluation

logger = logging.getLogger(__name__)

FINISHED_STATUSES = {"FT", "AET", "PEN"}
MODEL_VERSION = "eval_v1"


def _outcome(home: int, away: int) -> str:
    if home > away:
        return "H"
    if home == away:
        return "D"
    return "A"


def _predicted_outcome(p_home: float, p_draw: float, p_away: float) -> str:
    probs = [("H", p_home), ("D", p_draw), ("A", p_away)]
    return max(probs, key=lambda x: x[1])[0]


async def evaluate_fixture(db: AsyncSession, fixture_id: int) -> bool:
    """
    Compute and upsert pattern evaluation for one finished fixture.
    Returns True if evaluation was written, False if skipped (missing data).
    """
    fixture = await db.get(Fixture, fixture_id)
    if fixture is None or fixture.status_short not in FINISHED_STATUSES:
        return False
    if fixture.home_score is None or fixture.away_score is None:
        return False

    mrp_row = await db.execute(
        select(FixtureMatchResultProbability).where(
            FixtureMatchResultProbability.fixture_id == fixture_id
        )
    )
    mrp = mrp_row.scalar_one_or_none()
    if mrp is None:
        return False

    sl_row = await db.execute(
        select(FixtureScorelineDistribution).where(
            FixtureScorelineDistribution.fixture_id == fixture_id
        )
    )
    sl = sl_row.scalar_one_or_none()

    home_score: int = fixture.home_score
    away_score: int = fixture.away_score
    total_goals: int = home_score + away_score

    # Goal probability per team (for "team scores" markets)
    gp_rows = (await db.execute(
        select(FixtureGoalProbability).where(
            FixtureGoalProbability.fixture_id == fixture_id
        )
    )).scalars().all()
    gp_map = {gp.team_id: gp for gp in gp_rows}
    gp_home = gp_map.get(fixture.home_team_id)
    gp_away = gp_map.get(fixture.away_team_id)

    p_home = float(mrp.p_home_win)
    p_draw = float(mrp.p_draw)
    p_away = float(mrp.p_away_win)
    p_over_25 = float(mrp.p_over_25)
    p_over_15 = float(mrp.p_over_15) if mrp.p_over_15 is not None else None
    p_btts = float(mrp.p_btts)
    p_home_scores = float(gp_home.p_ge_1_goal) if gp_home else None
    p_away_scores = float(gp_away.p_ge_1_goal) if gp_away else None

    # ── 1X2 ──────────────────────────────────────────────────────────────────
    actual = _outcome(home_score, away_score)
    predicted = _predicted_outcome(p_home, p_draw, p_away)
    outcome_correct = actual == predicted
    p_actual = {"H": p_home, "D": p_draw, "A": p_away}[actual]
    log_loss = -math.log(max(p_actual, 1e-9))

    # Brier score for 1X2 (sum of squared differences over all outcomes)
    i_h = 1.0 if actual == "H" else 0.0
    i_d = 1.0 if actual == "D" else 0.0
    i_a = 1.0 if actual == "A" else 0.0
    brier_score = (p_home - i_h) ** 2 + (p_draw - i_d) ** 2 + (p_away - i_a) ** 2

    # ── Goals ─────────────────────────────────────────────────────────────────
    if sl is not None:
        predicted_total = float(sl.lambda_home) + float(sl.lambda_away)
        predicted_score = sl.most_likely_score
        predicted_score_prob = float(sl.most_likely_score_prob)
    else:
        predicted_total = 2.6  # fallback
        predicted_score = None
        predicted_score_prob = None

    goals_diff = abs(predicted_total - total_goals)
    actual_score_str = f"{home_score}-{away_score}"
    score_correct = predicted_score == actual_score_str

    # ── Doppelte Chance ───────────────────────────────────────────────────────
    dc_options = [
        ("1X", p_home + p_draw),
        ("X2", p_draw + p_away),
        ("12", p_home + p_away),
    ]
    dc_prediction, dc_prob = max(dc_options, key=lambda x: x[1])
    dc_covers = {"1X": {"H", "D"}, "X2": {"D", "A"}, "12": {"H", "A"}}
    dc_correct = actual in dc_covers[dc_prediction]

    # ── Over/Under 2.5 ────────────────────────────────────────────────────────
    predicted_over_25 = p_over_25 > 0.5
    actual_over_25 = total_goals > 2
    over_25_correct = predicted_over_25 == actual_over_25

    # ── Over/Under 1.5 ────────────────────────────────────────────────────────
    if p_over_15 is not None:
        predicted_over_15 = p_over_15 > 0.55   # slightly raised threshold
        actual_over_15 = total_goals > 1
        over_15_correct = predicted_over_15 == actual_over_15
    else:
        predicted_over_15 = actual_over_15 = over_15_correct = None

    # ── BTTS ──────────────────────────────────────────────────────────────────
    predicted_btts = p_btts > 0.5
    actual_btts = home_score > 0 and away_score > 0
    btts_correct = predicted_btts == actual_btts

    # ── Team scores ───────────────────────────────────────────────────────────
    if p_home_scores is not None:
        predicted_home_scores = p_home_scores > 0.5
        actual_home_scores = home_score > 0
        home_scores_correct = predicted_home_scores == actual_home_scores
    else:
        predicted_home_scores = actual_home_scores = home_scores_correct = None

    if p_away_scores is not None:
        predicted_away_scores = p_away_scores > 0.5
        actual_away_scores = away_score > 0
        away_scores_correct = predicted_away_scores == actual_away_scores
    else:
        predicted_away_scores = actual_away_scores = away_scores_correct = None

    values = dict(
        fixture_id=fixture_id,
        actual_outcome=actual,
        predicted_outcome=predicted,
        outcome_correct=outcome_correct,
        p_home_win=round(p_home, 4),
        p_draw=round(p_draw, 4),
        p_away_win=round(p_away, 4),
        p_actual_outcome=round(p_actual, 4),
        log_loss=round(log_loss, 6),
        brier_score=round(brier_score, 6),
        predicted_total_goals=round(predicted_total, 3),
        actual_total_goals=total_goals,
        goals_diff=round(goals_diff, 3),
        dc_prediction=dc_prediction,
        dc_prob=round(dc_prob, 4),
        dc_correct=dc_correct,
        p_over_25=round(p_over_25, 4),
        predicted_over_25=predicted_over_25,
        actual_over_25=actual_over_25,
        over_25_correct=over_25_correct,
        p_over_15=round(p_over_15, 4) if p_over_15 is not None else None,
        predicted_over_15=predicted_over_15,
        actual_over_15=actual_over_15,
        over_15_correct=over_15_correct,
        p_btts=round(p_btts, 4),
        predicted_btts=predicted_btts,
        actual_btts=actual_btts,
        btts_correct=btts_correct,
        p_home_scores=round(p_home_scores, 4) if p_home_scores is not None else None,
        predicted_home_scores=predicted_home_scores,
        actual_home_scores=actual_home_scores,
        home_scores_correct=home_scores_correct,
        p_away_scores=round(p_away_scores, 4) if p_away_scores is not None else None,
        predicted_away_scores=predicted_away_scores,
        actual_away_scores=actual_away_scores,
        away_scores_correct=away_scores_correct,
        predicted_score=predicted_score,
        predicted_score_prob=round(predicted_score_prob, 4) if predicted_score_prob else None,
        actual_score=actual_score_str,
        score_correct=score_correct,
        computed_at=datetime.utcnow(),
        model_version=MODEL_VERSION,
    )

    stmt = pg_insert(FixturePatternEvaluation).values(**values).on_conflict_do_update(
        constraint="uq_fixture_pattern_evaluation",
        set_={k: v for k, v in values.items() if k != "fixture_id"},
    )
    await db.execute(stmt)
    await db.commit()
    return True


async def evaluate_backfill(
    season_year: int = 2025,
    force: bool = False,
    concurrency: int = 20,
) -> dict:
    """
    Backfill evaluations for ALL finished fixtures with MRP data.

    - Only processes fixtures that have FixtureMatchResultProbability data.
    - Skips fixtures that already have an evaluation (unless force=True).
    - Runs with asyncio concurrency for speed.

    Returns summary: evaluated, skipped, errors, total_eligible.
    """
    # Find all finished fixtures that have MRP (needed for evaluation)
    async with AsyncSessionLocal() as db:
        stmt = (
            select(FixtureMatchResultProbability.fixture_id)
            .join(Fixture, Fixture.id == FixtureMatchResultProbability.fixture_id)
            .where(
                Fixture.season_year == season_year,
                Fixture.status_short.in_(FINISHED_STATUSES),
                Fixture.home_score.is_not(None),
                Fixture.away_score.is_not(None),
            )
            .order_by(Fixture.kickoff_utc)
        )
        result = await db.execute(stmt)
        all_ids = [row[0] for row in result.all()]

    if not all_ids:
        return {"evaluated": 0, "skipped": 0, "errors": 0, "total_eligible": 0}

    # If not forcing, exclude already-evaluated fixtures
    if not force:
        async with AsyncSessionLocal() as db:
            existing_result = await db.execute(
                select(FixturePatternEvaluation.fixture_id)
                .where(FixturePatternEvaluation.fixture_id.in_(all_ids))
            )
            existing_ids = {row[0] for row in existing_result.all()}
        to_process = [fid for fid in all_ids if fid not in existing_ids]
        skipped_initial = len(existing_ids)
    else:
        to_process = all_ids
        skipped_initial = 0

    total_eligible = len(all_ids)
    logger.info(
        f"Evaluation backfill: {len(to_process)} to process, "
        f"{skipped_initial} already done, season={season_year}"
    )

    if not to_process:
        return {
            "evaluated": 0,
            "skipped": skipped_initial,
            "errors": 0,
            "total_eligible": total_eligible,
        }

    semaphore = asyncio.Semaphore(concurrency)
    result_counts = {"evaluated": 0, "skipped": skipped_initial, "errors": 0}

    async def process(fid: int):
        async with semaphore:
            try:
                async with AsyncSessionLocal() as db:
                    ok = await evaluate_fixture(db, fid)
                if ok:
                    result_counts["evaluated"] += 1
                else:
                    result_counts["skipped"] += 1
            except Exception as exc:
                logger.error(f"Backfill eval failed for fixture {fid}: {exc}")
                result_counts["errors"] += 1

    await asyncio.gather(*[process(fid) for fid in to_process])

    logger.info(
        f"Backfill complete: {result_counts['evaluated']} evaluated, "
        f"{result_counts['skipped']} skipped, {result_counts['errors']} errors"
    )
    return {**result_counts, "total_eligible": total_eligible}


async def evaluate_for_date(target_date: date, season_year: int = 2025) -> dict:
    """Evaluate all finished fixtures on target_date that have MRP data."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Fixture.id)
            .where(
                Fixture.season_year == season_year,
                cast(Fixture.kickoff_utc, Date) == target_date,
                Fixture.status_short.in_(FINISHED_STATUSES),
            )
            .order_by(Fixture.kickoff_utc)
        )
        fixture_ids = [row[0] for row in result.all()]

    if not fixture_ids:
        return {"evaluated": 0, "skipped": 0, "total": 0}

    evaluated = 0
    skipped = 0
    for fid in fixture_ids:
        async with AsyncSessionLocal() as db:
            ok = await evaluate_fixture(db, fid)
        if ok:
            evaluated += 1
        else:
            skipped += 1

    return {"evaluated": evaluated, "skipped": skipped, "total": len(fixture_ids)}
