from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FixtureH2H(Base):
    __tablename__ = "fixture_h2h"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fixture_id: Mapped[int] = mapped_column(Integer, ForeignKey("fixtures.id"), nullable=False, unique=True)
    home_team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), nullable=False)
    away_team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), nullable=False)

    h2h_matches_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    h2h_home_wins: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    h2h_draws: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    h2h_away_wins: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    h2h_avg_goals_home: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False, default=0.0)
    h2h_avg_goals_away: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False, default=0.0)
    h2h_avg_total_goals: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False, default=0.0)

    h2h_btts_rate: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False, default=0.0)
    h2h_over_25_rate: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False, default=0.0)

    h2h_home_win_pct: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False, default=0.0)
    h2h_draw_pct: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False, default=0.0)
    h2h_away_win_pct: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False, default=0.0)

    # h2h_score: Stärke des Heimteams in Direktduellen (0-100)
    h2h_score: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False, default=50.0)

    window_years: Mapped[int] = mapped_column(Integer, nullable=False, default=5)

    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    model_version: Mapped[str] = mapped_column(String(40), nullable=False, default="h2h_v1")

    __table_args__ = (
        UniqueConstraint("fixture_id", name="uq_fixture_h2h"),
    )
