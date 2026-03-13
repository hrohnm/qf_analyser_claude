from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FixtureValueBet(Base):
    __tablename__ = "fixture_value_bet"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fixture_id: Mapped[int] = mapped_column(Integer, ForeignKey("fixtures.id"), nullable=False)

    market_name: Mapped[str] = mapped_column(String(100), nullable=False)
    bet_value: Mapped[str] = mapped_column(String(100), nullable=False)
    bet_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    model_prob: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    bookmaker_odd: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    implied_prob: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    vig: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    fair_odd: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    edge: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    expected_value: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    kelly_fraction: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)

    tier: Mapped[str] = mapped_column(String(20), nullable=False)  # no_value / marginal / value / strong_value

    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    model_version: Mapped[str] = mapped_column(String(40), nullable=False, default="value_bet_v1")

    __table_args__ = (
        UniqueConstraint("fixture_id", "market_name", "bet_value", name="uq_fixture_value_bet"),
    )
