from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FixtureInjury(Base):
    __tablename__ = "fixture_injuries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fixture_id: Mapped[int] = mapped_column(Integer, ForeignKey("fixtures.id"), nullable=False)
    team_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("teams.id"))
    player_id: Mapped[int | None] = mapped_column(Integer)

    team_name: Mapped[str | None] = mapped_column(String(200))
    player_name: Mapped[str | None] = mapped_column(String(200))
    injury_type: Mapped[str | None] = mapped_column(String(60))  # Missing Fixture | Questionable
    injury_reason: Mapped[str | None] = mapped_column(String(300))

    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "fixture_id", "team_id", "player_id", "injury_type", "injury_reason",
            name="uq_fixture_injury_entry",
        ),
    )
