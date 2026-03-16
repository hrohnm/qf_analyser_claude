from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FixtureTopScorerPattern(Base):
    __tablename__ = "fixture_top_scorer_pattern"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fixture_id: Mapped[int] = mapped_column(Integer, ForeignKey("fixtures.id"), nullable=False)
    home_team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), nullable=False)
    away_team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), nullable=False)

    top_scorer: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    home_candidates: Mapped[list | None] = mapped_column(JSON, nullable=True)
    away_candidates: Mapped[list | None] = mapped_column(JSON, nullable=True)

    home_penalties_per_match: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    away_penalties_per_match: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    home_penalty_conversion_share: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    away_penalty_conversion_share: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    model_confidence: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False, default=0.2)
    sample_size_home: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sample_size_away: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    model_version: Mapped[str] = mapped_column(String(40), nullable=False, default="top_scorer_v1")

    __table_args__ = (
        UniqueConstraint("fixture_id", name="uq_fixture_top_scorer_pattern"),
    )
