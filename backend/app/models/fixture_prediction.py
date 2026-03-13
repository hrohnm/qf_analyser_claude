from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FixturePrediction(Base):
    __tablename__ = "fixture_predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fixture_id: Mapped[int] = mapped_column(Integer, ForeignKey("fixtures.id"), nullable=False)

    winner_team_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("teams.id"))
    winner_name: Mapped[str | None] = mapped_column(String(200))
    winner_comment: Mapped[str | None] = mapped_column(String(300))
    win_or_draw: Mapped[bool | None] = mapped_column(Boolean)
    under_over: Mapped[str | None] = mapped_column(String(30))
    advice: Mapped[str | None] = mapped_column(String(500))

    percent_home: Mapped[float | None] = mapped_column(Numeric(5, 2))
    percent_draw: Mapped[float | None] = mapped_column(Numeric(5, 2))
    percent_away: Mapped[float | None] = mapped_column(Numeric(5, 2))

    # Predicted goal handicap (e.g. "-2.5" / "-1.5")
    goals_pred_home: Mapped[str | None] = mapped_column(String(10))
    goals_pred_away: Mapped[str | None] = mapped_column(String(10))

    # Comparison block (all as %-floats)
    cmp_form_home: Mapped[float | None] = mapped_column(Numeric(5, 2))
    cmp_form_away: Mapped[float | None] = mapped_column(Numeric(5, 2))
    cmp_att_home: Mapped[float | None] = mapped_column(Numeric(5, 2))
    cmp_att_away: Mapped[float | None] = mapped_column(Numeric(5, 2))
    cmp_def_home: Mapped[float | None] = mapped_column(Numeric(5, 2))
    cmp_def_away: Mapped[float | None] = mapped_column(Numeric(5, 2))
    cmp_poisson_home: Mapped[float | None] = mapped_column(Numeric(5, 2))
    cmp_poisson_away: Mapped[float | None] = mapped_column(Numeric(5, 2))
    cmp_h2h_home: Mapped[float | None] = mapped_column(Numeric(5, 2))
    cmp_h2h_away: Mapped[float | None] = mapped_column(Numeric(5, 2))
    cmp_goals_home: Mapped[float | None] = mapped_column(Numeric(5, 2))
    cmp_goals_away: Mapped[float | None] = mapped_column(Numeric(5, 2))
    cmp_total_home: Mapped[float | None] = mapped_column(Numeric(5, 2))
    cmp_total_away: Mapped[float | None] = mapped_column(Numeric(5, 2))

    # Last 5 stats – home team
    home_last5_form: Mapped[float | None] = mapped_column(Numeric(5, 2))
    home_last5_att: Mapped[float | None] = mapped_column(Numeric(5, 2))
    home_last5_def: Mapped[float | None] = mapped_column(Numeric(5, 2))
    home_last5_goals_for_avg: Mapped[float | None] = mapped_column(Numeric(5, 2))
    home_last5_goals_against_avg: Mapped[float | None] = mapped_column(Numeric(5, 2))

    # Last 5 stats – away team
    away_last5_form: Mapped[float | None] = mapped_column(Numeric(5, 2))
    away_last5_att: Mapped[float | None] = mapped_column(Numeric(5, 2))
    away_last5_def: Mapped[float | None] = mapped_column(Numeric(5, 2))
    away_last5_goals_for_avg: Mapped[float | None] = mapped_column(Numeric(5, 2))
    away_last5_goals_against_avg: Mapped[float | None] = mapped_column(Numeric(5, 2))

    # Season stats – home team
    home_season_form: Mapped[str | None] = mapped_column(String(100))
    home_clean_sheet_home: Mapped[int | None] = mapped_column(Integer)
    home_clean_sheet_away: Mapped[int | None] = mapped_column(Integer)
    home_clean_sheet_total: Mapped[int | None] = mapped_column(Integer)
    home_failed_to_score_total: Mapped[int | None] = mapped_column(Integer)
    home_wins_home: Mapped[int | None] = mapped_column(Integer)
    home_wins_away: Mapped[int | None] = mapped_column(Integer)
    home_draws_total: Mapped[int | None] = mapped_column(Integer)
    home_loses_total: Mapped[int | None] = mapped_column(Integer)
    home_goals_for_avg_total: Mapped[float | None] = mapped_column(Numeric(5, 2))
    home_goals_against_avg_total: Mapped[float | None] = mapped_column(Numeric(5, 2))

    # Season stats – away team
    away_season_form: Mapped[str | None] = mapped_column(String(100))
    away_clean_sheet_home: Mapped[int | None] = mapped_column(Integer)
    away_clean_sheet_away: Mapped[int | None] = mapped_column(Integer)
    away_clean_sheet_total: Mapped[int | None] = mapped_column(Integer)
    away_failed_to_score_total: Mapped[int | None] = mapped_column(Integer)
    away_wins_home: Mapped[int | None] = mapped_column(Integer)
    away_wins_away: Mapped[int | None] = mapped_column(Integer)
    away_draws_total: Mapped[int | None] = mapped_column(Integer)
    away_loses_total: Mapped[int | None] = mapped_column(Integer)
    away_goals_for_avg_total: Mapped[float | None] = mapped_column(Numeric(5, 2))
    away_goals_against_avg_total: Mapped[float | None] = mapped_column(Numeric(5, 2))

    raw_json: Mapped[dict | None] = mapped_column(JSON)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("fixture_id", name="uq_fixture_predictions_fixture_id"),
    )
