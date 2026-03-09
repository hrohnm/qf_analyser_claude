from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FixturePrediction(Base):
    __tablename__ = "fixture_predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fixture_id: Mapped[int] = mapped_column(Integer, ForeignKey("fixtures.id"), nullable=False)

    winner_team_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("teams.id"))
    winner_name: Mapped[str | None] = mapped_column(String(200))
    winner_comment: Mapped[str | None] = mapped_column(String(300))
    win_or_draw: Mapped[bool | None] = mapped_column(Boolean)
    under_over: Mapped[str | None] = mapped_column(String(30))
    advice: Mapped[str | None] = mapped_column(String(500))

    percent_home: Mapped[float | None] = mapped_column(Numeric(5, 2))
    percent_draw: Mapped[float | None] = mapped_column(Numeric(5, 2))
    percent_away: Mapped[float | None] = mapped_column(Numeric(5, 2))

    raw_json: Mapped[dict | None] = mapped_column(JSON)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("fixture_id", name="uq_fixture_predictions_fixture_id"),
    )
