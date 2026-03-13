from datetime import datetime
from sqlalchemy import Integer, String, JSON, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class FixtureOdds(Base):
    __tablename__ = "fixture_odds"
    __table_args__ = (
        UniqueConstraint("fixture_id", "bookmaker_id", "bet_id", name="uq_fixture_odds_fixture_bookmaker_bet"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fixture_id: Mapped[int] = mapped_column(Integer, ForeignKey("fixtures.id"), nullable=False)
    bookmaker_id: Mapped[int] = mapped_column(Integer, nullable=False)
    bookmaker_name: Mapped[str] = mapped_column(String(100), nullable=False)
    bet_id: Mapped[int] = mapped_column(Integer, nullable=False)
    bet_name: Mapped[str] = mapped_column(String(200), nullable=False)
    values: Mapped[list] = mapped_column(JSON, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
