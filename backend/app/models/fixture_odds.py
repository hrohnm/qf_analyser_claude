from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FixtureOdds(Base):
    """
    Pre-match odds from a bookmaker for a specific fixture and bet type.
    One row per (fixture, bookmaker, bet_type).
    values: list of {value: str, odd: str} – e.g. [{value: "Home", odd: "1.85"}, ...]
    For Anytime Scorer, value contains the player name.
    """
    __tablename__ = "fixture_odds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fixture_id: Mapped[int] = mapped_column(Integer, ForeignKey("fixtures.id"), nullable=False)
    bookmaker_id: Mapped[int] = mapped_column(Integer, nullable=False)
    bookmaker_name: Mapped[str] = mapped_column(String(100), nullable=False)
    bet_id: Mapped[int] = mapped_column(Integer, nullable=False)
    bet_name: Mapped[str] = mapped_column(String(200), nullable=False)
    values: Mapped[list] = mapped_column(JSON, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("fixture_id", "bookmaker_id", "bet_id",
                         name="uq_fixture_odds_fixture_bookmaker_bet"),
    )
