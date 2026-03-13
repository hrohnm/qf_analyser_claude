from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TeamHomeAdvantage(Base):
    __tablename__ = "team_home_advantage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), nullable=False)
    league_id: Mapped[int] = mapped_column(Integer, ForeignKey("leagues.id"), nullable=False)
    season_year: Mapped[int] = mapped_column(Integer, nullable=False)

    home_ppg: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False, default=0.0)
    away_ppg: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False, default=0.0)
    advantage_factor: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False, default=1.0)
    league_avg_factor: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False, default=1.0)
    normalized_factor: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False, default=1.0)

    games_home: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    games_away: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    tier: Mapped[str] = mapped_column(String(20), nullable=False, default="neutral")
    # "fortress"/"home_strong"/"neutral"/"road_team"

    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    model_version: Mapped[str] = mapped_column(String(40), nullable=False, default="home_adv_v1")

    __table_args__ = (
        UniqueConstraint("team_id", "league_id", "season_year", name="uq_team_home_advantage"),
    )
