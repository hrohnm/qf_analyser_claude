from datetime import datetime, date
from sqlalchemy import Integer, String, Text, DateTime, Date, UniqueConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class DayBettingSlip(Base):
    """Stored betting slips generated for one day and one source."""
    __tablename__ = "day_betting_slips"
    __table_args__ = (
        UniqueConstraint("slip_date", "source", name="uq_day_betting_slip_date_source"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slip_date: Mapped[date] = mapped_column(Date, nullable=False)

    # List of generated slip objects:
    # [{
    #   "slip_nr": 1,
    #   "target_odd": 10.0,
    #   "combined_odd": 9.85,
    #   "reasoning": "...",
    #   "picks": [{
    #     "fixture_id": 123, "home": "A", "away": "B",
    #     "market": "...", "pick": "...",
    #     "bet_id": 1, "bet_value": "Home", "odd": 1.85,
    #     "betbuilder": false,   # true = same fixture as previous pick
    #     "result": null
    #   }]
    # }]
    slips: Mapped[list] = mapped_column(JSON, nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="ai")  # 'ai' | 'pattern'

    model_version: Mapped[str] = mapped_column(String(50), nullable=False, default="claude-sonnet-4-6")
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
