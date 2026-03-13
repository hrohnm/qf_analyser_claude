from datetime import datetime, date
from sqlalchemy import Integer, String, Date, DateTime, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class PlacedBet(Base):
    """Tracks which betting slips were actually played and their outcomes."""
    __tablename__ = "placed_bets"
    __table_args__ = (
        UniqueConstraint("slip_date", "source", "slip_nr", name="uq_placed_bet"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slip_date: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)        # 'ai' | 'pattern'
    slip_nr: Mapped[int] = mapped_column(Integer, nullable=False)
    slip_name: Mapped[str | None] = mapped_column(String(100))             # e.g. "Verdoppler Ü1,5"
    combined_odd: Mapped[float] = mapped_column(Numeric(8, 3), nullable=False)
    stake: Mapped[float | None] = mapped_column(Numeric(8, 2))             # optional stake amount
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="placed")
    # status: 'placed' | 'won' | 'lost' | 'void'

    placed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime)
