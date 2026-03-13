from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FixtureMatchResultProbability(Base):
    __tablename__ = "fixture_match_result_probability"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fixture_id: Mapped[int] = mapped_column(Integer, ForeignKey("fixtures.id"), nullable=False, unique=True)

    # Final combined probabilities
    p_home_win: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    p_draw: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    p_away_win: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)

    p_btts: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    p_over_25: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    p_over_15: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    p_over_35: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)

    p_home_clean_sheet: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    p_away_clean_sheet: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)

    # Source weights
    src_goal_prob_weight: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False, default=0.35)
    src_elo_weight: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False, default=0.25)
    src_form_weight: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False, default=0.20)
    src_h2h_weight: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False, default=0.10)
    src_home_adv_weight: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False, default=0.05)
    src_injury_weight: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False, default=0.05)

    # Component transparency
    elo_home_prob: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    elo_draw_prob: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    elo_away_prob: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)

    form_home_score: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    form_away_score: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)

    h2h_home_pct: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    home_adv_factor: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    injury_delta: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)

    # How complete input data is (0-1)
    confidence: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False, default=0.3)

    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    model_version: Mapped[str] = mapped_column(String(40), nullable=False, default="mrp_v1")

    __table_args__ = (
        UniqueConstraint("fixture_id", name="uq_fixture_match_result_probability"),
    )
