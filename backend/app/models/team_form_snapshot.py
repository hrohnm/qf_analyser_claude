from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TeamFormSnapshot(Base):
    __tablename__ = "team_form_snapshot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), nullable=False)
    league_id: Mapped[int] = mapped_column(Integer, ForeignKey("leagues.id"), nullable=False)
    season_year: Mapped[int] = mapped_column(Integer, nullable=False)
    window_size: Mapped[int] = mapped_column(Integer, nullable=False)
    scope: Mapped[str] = mapped_column(String(20), nullable=False)  # overall | home | away

    form_score: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    result_score: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)
    performance_score: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)
    trend_score: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)
    opponent_strength_score: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)
    elo_adjusted_result_score: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)

    form_trend: Mapped[str] = mapped_column(String(10), nullable=False)  # up | flat | down
    form_bucket: Mapped[str] = mapped_column(String(20), nullable=False)  # schwach | mittel | stark
    games_considered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    model_version: Mapped[str] = mapped_column(String(40), nullable=False, default="team_form_v1")

    __table_args__ = (
        UniqueConstraint(
            "team_id",
            "league_id",
            "season_year",
            "window_size",
            "scope",
            name="uq_team_form_snapshot",
        ),
    )
