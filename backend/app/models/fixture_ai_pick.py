from datetime import datetime
from sqlalchemy import Integer, String, Text, DateTime, ForeignKey, UniqueConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class FixtureAiPick(Base):
    __tablename__ = "fixture_ai_picks"
    __table_args__ = (
        UniqueConstraint("fixture_id", name="uq_fixture_ai_picks_fixture_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fixture_id: Mapped[int] = mapped_column(Integer, ForeignKey("fixtures.id"), nullable=False)

    picks: Mapped[list] = mapped_column(JSON, nullable=False)         # 5 picks
    top_scorer: Mapped[dict | None] = mapped_column(JSON)             # {player_name, team, reasoning}
    summary: Mapped[str | None] = mapped_column(Text)                 # Gesamteinschätzung
    model_version: Mapped[str] = mapped_column(String(50), nullable=False, default="claude-sonnet-4-6")
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
