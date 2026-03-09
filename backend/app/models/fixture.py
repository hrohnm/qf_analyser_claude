from datetime import datetime
from sqlalchemy import Integer, String, SmallInteger, DateTime, ForeignKey, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Fixture(Base):
    __tablename__ = "fixtures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # api-football fixture_id
    league_id: Mapped[int] = mapped_column(Integer, ForeignKey("leagues.id"), nullable=False)
    season_year: Mapped[int] = mapped_column(Integer, nullable=False)
    home_team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), nullable=False)
    away_team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), nullable=False)

    kickoff_utc: Mapped[datetime | None] = mapped_column(DateTime)
    round: Mapped[str | None] = mapped_column(String(50))
    matchday: Mapped[int | None] = mapped_column(SmallInteger)  # extracted number from round string

    # Status: NS=Not Started, 1H, HT, 2H, FT, AET, PEN, CANC, PST=Postponed
    status_short: Mapped[str | None] = mapped_column(String(10))
    status_long: Mapped[str | None] = mapped_column(String(50))
    elapsed: Mapped[int | None] = mapped_column(SmallInteger)

    # Scores
    home_score: Mapped[int | None] = mapped_column(SmallInteger)
    away_score: Mapped[int | None] = mapped_column(SmallInteger)
    home_ht_score: Mapped[int | None] = mapped_column(SmallInteger)
    away_ht_score: Mapped[int | None] = mapped_column(SmallInteger)

    referee: Mapped[str | None] = mapped_column(String(100))
    venue_name: Mapped[str | None] = mapped_column(String(200))

    raw_json: Mapped[dict | None] = mapped_column(JSON)  # full API response cached
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    league: Mapped["League"] = relationship("League", back_populates="fixtures")
    home_team: Mapped["Team"] = relationship("Team", foreign_keys=[home_team_id], back_populates="home_fixtures")
    away_team: Mapped["Team"] = relationship("Team", foreign_keys=[away_team_id], back_populates="away_fixtures")

    __table_args__ = (
        Index("idx_fixtures_league_season", "league_id", "season_year"),
        Index("idx_fixtures_kickoff", "kickoff_utc"),
        Index("idx_fixtures_status", "status_short"),
        Index("idx_fixtures_home_team", "home_team_id"),
        Index("idx_fixtures_away_team", "away_team_id"),
    )

    def __repr__(self) -> str:
        return f"<Fixture id={self.id} {self.home_team_id}v{self.away_team_id} {self.kickoff_utc}>"
