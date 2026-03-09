from datetime import datetime
from sqlalchemy import Integer, SmallInteger, DateTime, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FixtureStatistics(Base):
    __tablename__ = "fixture_statistics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fixture_id: Mapped[int] = mapped_column(Integer, ForeignKey("fixtures.id"), nullable=False)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), nullable=False)

    shots_on_goal: Mapped[int | None] = mapped_column(SmallInteger)
    shots_off_goal: Mapped[int | None] = mapped_column(SmallInteger)
    shots_total: Mapped[int | None] = mapped_column(SmallInteger)
    shots_blocked: Mapped[int | None] = mapped_column(SmallInteger)
    shots_inside_box: Mapped[int | None] = mapped_column(SmallInteger)
    shots_outside_box: Mapped[int | None] = mapped_column(SmallInteger)
    fouls: Mapped[int | None] = mapped_column(SmallInteger)
    corner_kicks: Mapped[int | None] = mapped_column(SmallInteger)
    offsides: Mapped[int | None] = mapped_column(SmallInteger)
    ball_possession: Mapped[float | None] = mapped_column(Numeric(5, 2))  # e.g. 54.0
    yellow_cards: Mapped[int | None] = mapped_column(SmallInteger)
    red_cards: Mapped[int | None] = mapped_column(SmallInteger)
    goalkeeper_saves: Mapped[int | None] = mapped_column(SmallInteger)
    passes_total: Mapped[int | None] = mapped_column(Integer)
    passes_accurate: Mapped[int | None] = mapped_column(Integer)
    pass_accuracy: Mapped[float | None] = mapped_column(Numeric(5, 2))
    expected_goals: Mapped[float | None] = mapped_column(Numeric(6, 3))

    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("fixture_id", "team_id", name="uq_fixture_stats_fixture_team"),
    )
