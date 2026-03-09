from datetime import datetime
from sqlalchemy import Integer, SmallInteger, String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FixtureEvent(Base):
    __tablename__ = "fixture_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fixture_id: Mapped[int] = mapped_column(Integer, ForeignKey("fixtures.id"), nullable=False)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), nullable=False)

    elapsed: Mapped[int | None] = mapped_column(SmallInteger)
    elapsed_extra: Mapped[int | None] = mapped_column(SmallInteger)

    event_type: Mapped[str | None] = mapped_column(String(30))   # Goal, Card, subst, Var
    detail: Mapped[str | None] = mapped_column(String(100))       # Normal Goal, Yellow Card, …
    comments: Mapped[str | None] = mapped_column(String(300))

    player_id: Mapped[int | None] = mapped_column(Integer)        # no FK – player may not be in DB
    player_name: Mapped[str | None] = mapped_column(String(100))
    assist_id: Mapped[int | None] = mapped_column(Integer)
    assist_name: Mapped[str | None] = mapped_column(String(100))

    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
