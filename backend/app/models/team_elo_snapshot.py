from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TeamEloSnapshot(Base):
    __tablename__ = "team_elo_snapshot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), nullable=False)
    league_id: Mapped[int] = mapped_column(Integer, ForeignKey("leagues.id"), nullable=False)
    season_year: Mapped[int] = mapped_column(Integer, nullable=False)

    elo_overall: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False, default=1500.0)
    elo_home: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False, default=1500.0)
    elo_away: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False, default=1500.0)

    games_played: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    games_home: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    games_away: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    elo_delta_last_5: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False, default=0.0)
    strength_tier: Mapped[str] = mapped_column(String(20), nullable=False, default="average")

    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    model_version: Mapped[str] = mapped_column(String(40), nullable=False, default="team_elo_v1")

    __table_args__ = (
        UniqueConstraint("team_id", "league_id", "season_year", name="uq_team_elo_snapshot"),
    )
