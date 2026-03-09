from datetime import datetime
from sqlalchemy import Integer, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # api-football team_id
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(50))
    country: Mapped[str | None] = mapped_column(String(50))
    logo_url: Mapped[str | None] = mapped_column(String(500))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    home_fixtures: Mapped[list["Fixture"]] = relationship("Fixture", foreign_keys="Fixture.home_team_id", back_populates="home_team")
    away_fixtures: Mapped[list["Fixture"]] = relationship("Fixture", foreign_keys="Fixture.away_team_id", back_populates="away_team")

    def __repr__(self) -> str:
        return f"<Team id={self.id} name={self.name!r}>"
