from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FixtureGoalProbability(Base):
    __tablename__ = "fixture_goal_probability"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fixture_id: Mapped[int] = mapped_column(Integer, ForeignKey("fixtures.id"), nullable=False)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), nullable=False)
    is_home: Mapped[bool] = mapped_column(Boolean, nullable=False)
    season_year: Mapped[int] = mapped_column(Integer, nullable=False)
    league_id: Mapped[int] = mapped_column(Integer, ForeignKey("leagues.id"), nullable=False)

    lambda_weighted: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    p_ge_1_goal: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    p_ge_2_goals: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    p_ge_3_goals: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False, default=0.2)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    model_version: Mapped[str] = mapped_column(String(40), nullable=False, default="goal_prob_v1")

    __table_args__ = (
        UniqueConstraint("fixture_id", "team_id", name="uq_fixture_goal_probability"),
    )
