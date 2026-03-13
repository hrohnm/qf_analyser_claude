from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TeamGoalTiming(Base):
    __tablename__ = "team_goal_timing"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), nullable=False)
    league_id: Mapped[int] = mapped_column(Integer, ForeignKey("leagues.id"), nullable=False)
    season_year: Mapped[int] = mapped_column(Integer, nullable=False)
    scope: Mapped[str] = mapped_column(String(10), nullable=False)  # "overall"/"home"/"away"

    games_played: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    goals_scored: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    goals_conceded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # JSON: {"0_15": {"goals": 3, "rate": 0.12, "index": 0.85}, ...}
    timing_attack: Mapped[dict | None] = mapped_column(JSON)
    timing_defense: Mapped[dict | None] = mapped_column(JSON)

    ht_attack_ratio: Mapped[float | None] = mapped_column(Numeric(6, 4))
    profil_typ: Mapped[str | None] = mapped_column(String(20))  # "starte_stark"/"finisher"/"ausgeglichen"
    p_goal_first_30: Mapped[float | None] = mapped_column(Numeric(6, 4))
    p_goal_last_15: Mapped[float | None] = mapped_column(Numeric(6, 4))

    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    model_version: Mapped[str] = mapped_column(String(40), nullable=False, default="goal_timing_v1")

    __table_args__ = (
        UniqueConstraint("team_id", "league_id", "season_year", "scope", name="uq_team_goal_timing"),
    )
