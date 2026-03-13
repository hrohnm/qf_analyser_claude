from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, SmallInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TeamSeasonProfile(Base):
    """
    Aggregated team profile for a league/season.

    Computed from fixture_statistics and fixture results.
    One row per (team_id, league_id, season_year).
    Provides attack, defense, and style metrics plus 0-100 composite ratings
    normalised within the league.
    """

    __tablename__ = "team_season_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), nullable=False)
    league_id: Mapped[int] = mapped_column(Integer, ForeignKey("leagues.id"), nullable=False)
    season_year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    games_played: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    # ── Attack ────────────────────────────────────────────────────────────────
    goals_scored: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    goals_scored_pg: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False)
    xg_for: Mapped[float | None] = mapped_column(Numeric(8, 3), nullable=True)
    xg_for_pg: Mapped[float | None] = mapped_column(Numeric(6, 3), nullable=True)
    shots_total_pg: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    shots_on_target_pg: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    shots_on_target_ratio: Mapped[float | None] = mapped_column(Numeric(6, 3), nullable=True)
    shot_conversion_rate: Mapped[float | None] = mapped_column(Numeric(6, 3), nullable=True)
    shots_inside_box_pg: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)

    # ── Defense ───────────────────────────────────────────────────────────────
    goals_conceded: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    goals_conceded_pg: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False)
    clean_sheets: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    clean_sheet_rate: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False)
    xg_against: Mapped[float | None] = mapped_column(Numeric(8, 3), nullable=True)
    xg_against_pg: Mapped[float | None] = mapped_column(Numeric(6, 3), nullable=True)
    shots_against_pg: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    shots_on_target_against_pg: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    gk_saves_pg: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)

    # ── Style / Intensity ─────────────────────────────────────────────────────
    possession_avg: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    passes_pg: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    pass_accuracy_avg: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    corners_pg: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    fouls_pg: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    yellow_cards_pg: Mapped[float | None] = mapped_column(Numeric(5, 3), nullable=True)
    red_cards_pg: Mapped[float | None] = mapped_column(Numeric(5, 3), nullable=True)
    offsides_pg: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)

    # ── xG Performance ────────────────────────────────────────────────────────
    # Positive = clinical finisher (scores more than xG predicts)
    xg_over_performance: Mapped[float | None] = mapped_column(Numeric(7, 3), nullable=True)
    # Positive = defense/GK better than xG against predicts
    xg_defense_performance: Mapped[float | None] = mapped_column(Numeric(7, 3), nullable=True)

    # ── Composite Ratings (0-100, z-score normalised within league) ───────────
    attack_rating: Mapped[float | None] = mapped_column(Numeric(5, 1), nullable=True)
    defense_rating: Mapped[float | None] = mapped_column(Numeric(5, 1), nullable=True)
    intensity_rating: Mapped[float | None] = mapped_column(Numeric(5, 1), nullable=True)

    # ── Metadata ─────────────────────────────────────────────────────────────
    computed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    model_version: Mapped[str] = mapped_column(String(40), nullable=False)

    __table_args__ = (
        UniqueConstraint("team_id", "league_id", "season_year", name="uq_team_season_profile"),
    )
