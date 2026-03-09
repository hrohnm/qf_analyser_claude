from datetime import datetime
from sqlalchemy import Integer, String, SmallInteger, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class League(Base):
    __tablename__ = "leagues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # api-football league_id
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    country: Mapped[str] = mapped_column(String(50), nullable=False)
    logo_url: Mapped[str | None] = mapped_column(String(500))
    tier: Mapped[int] = mapped_column(SmallInteger, nullable=False)  # 1=top, 2=second, 3=third
    current_season: Mapped[int | None] = mapped_column(Integer)      # e.g. 2024
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    fixtures: Mapped[list["Fixture"]] = relationship("Fixture", back_populates="league")

    def __repr__(self) -> str:
        return f"<League id={self.id} name={self.name!r} tier={self.tier}>"
