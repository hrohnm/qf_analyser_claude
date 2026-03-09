from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FixtureInjuryImpact(Base):
    __tablename__ = "fixture_injury_impacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fixture_id: Mapped[int] = mapped_column(Integer, ForeignKey("fixtures.id"), nullable=False)
    team_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("teams.id"))
    player_id: Mapped[int | None] = mapped_column(Integer)
    player_name: Mapped[str | None] = mapped_column(String(200))

    impact_score: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    impact_bucket: Mapped[str] = mapped_column(String(20), nullable=False)
    importance_score: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)
    contribution_score: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)
    replaceability_score: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)
    availability_factor: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)
    model_version: Mapped[str] = mapped_column(String(40), nullable=False, default="injury_impact_v1")

    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
