from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FixtureScorelineDistribution(Base):
    __tablename__ = "fixture_scoreline_distribution"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fixture_id: Mapped[int] = mapped_column(Integer, ForeignKey("fixtures.id"), nullable=False, unique=True)

    lambda_home: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    lambda_away: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)

    # JSON: {"0_0": 0.08, "1_0": 0.12, ...} for scores 0-0 to 4-4 (25 entries)
    p_matrix: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Derived from matrix
    p_home_win: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    p_draw: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    p_away_win: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)

    p_btts: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    p_over_15: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    p_over_25: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    p_over_35: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)

    p_home_clean_sheet: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    p_away_clean_sheet: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)

    most_likely_score: Mapped[str] = mapped_column(String(10), nullable=False)
    most_likely_score_prob: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)

    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    model_version: Mapped[str] = mapped_column(String(40), nullable=False, default="scoreline_v1")

    __table_args__ = (
        UniqueConstraint("fixture_id", name="uq_fixture_scoreline_distribution"),
    )
