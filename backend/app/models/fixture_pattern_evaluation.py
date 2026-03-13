from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FixturePatternEvaluation(Base):
    """Post-match accuracy check: predicted vs. actual for 1X2, goals, score, BTTS."""

    __tablename__ = "fixture_pattern_evaluation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fixture_id: Mapped[int] = mapped_column(Integer, ForeignKey("fixtures.id"), nullable=False, unique=True)

    # ── 1X2 ──────────────────────────────────────────────────────────────────
    actual_outcome: Mapped[str] = mapped_column(String(1), nullable=False)   # H / D / A
    predicted_outcome: Mapped[str] = mapped_column(String(1), nullable=False) # H / D / A
    outcome_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)

    p_home_win: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    p_draw: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    p_away_win: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    p_actual_outcome: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)

    # ── Scoring quality ───────────────────────────────────────────────────────
    log_loss: Mapped[float] = mapped_column(Numeric(10, 6), nullable=False)   # −ln(p_actual)
    brier_score: Mapped[float] = mapped_column(Numeric(10, 6), nullable=False) # sum of squared errors

    # ── Goals ─────────────────────────────────────────────────────────────────
    predicted_total_goals: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False)
    actual_total_goals: Mapped[int] = mapped_column(Integer, nullable=False)
    goals_diff: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False)  # abs(predicted - actual)

    # ── Doppelte Chance ───────────────────────────────────────────────────────
    dc_prediction: Mapped[str | None] = mapped_column(String(2), nullable=True)  # '1X' / 'X2' / '12'
    dc_prob: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    dc_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # ── Over/Under 2.5 ────────────────────────────────────────────────────────
    p_over_25: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    predicted_over_25: Mapped[bool] = mapped_column(Boolean, nullable=False)
    actual_over_25: Mapped[bool] = mapped_column(Boolean, nullable=False)
    over_25_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)

    # ── BTTS ──────────────────────────────────────────────────────────────────
    p_btts: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    predicted_btts: Mapped[bool] = mapped_column(Boolean, nullable=False)
    actual_btts: Mapped[bool] = mapped_column(Boolean, nullable=False)
    btts_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)

    # ── Over/Under 1.5 ────────────────────────────────────────────────────────
    p_over_15: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    predicted_over_15: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    actual_over_15: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    over_15_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # ── Team scores (≥ 1 goal) ────────────────────────────────────────────────
    p_home_scores: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    predicted_home_scores: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    actual_home_scores: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    home_scores_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    p_away_scores: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    predicted_away_scores: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    actual_away_scores: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    away_scores_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # ── Score prediction ──────────────────────────────────────────────────────
    predicted_score: Mapped[str | None] = mapped_column(String(10), nullable=True)
    predicted_score_prob: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    actual_score: Mapped[str] = mapped_column(String(10), nullable=False)
    score_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)

    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    model_version: Mapped[str] = mapped_column(String(40), nullable=False, default="eval_v1")

    __table_args__ = (
        UniqueConstraint("fixture_id", name="uq_fixture_pattern_evaluation"),
    )
