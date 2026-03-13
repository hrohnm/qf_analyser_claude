from __future__ import annotations

import math
from datetime import datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fixture import Fixture
from app.models.fixture_h2h import FixtureH2H

FINISHED_STATUSES = {"FT", "AET", "PEN"}
MODEL_VERSION = "h2h_v1"
WINDOW_YEARS = 5
MIN_MATCHES = 3
RECENCY_DECAY = 0.001  # exp(-0.001 * days)


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


async def compute_h2h_for_fixture(
    db: AsyncSession,
    fixture_id: int,
) -> dict:
    fixture = await db.get(Fixture, fixture_id)
    if fixture is None:
        return {"fixture_id": fixture_id, "rows": 0}

    home_team_id = fixture.home_team_id
    away_team_id = fixture.away_team_id

    cutoff = (fixture.kickoff_utc or datetime.utcnow()) - timedelta(days=WINDOW_YEARS * 365)

    # Find all historical h2h matches between the two teams
    stmt = (
        select(Fixture)
        .where(
            Fixture.status_short.in_(FINISHED_STATUSES),
            Fixture.id != fixture_id,
            or_(
                (Fixture.home_team_id == home_team_id) & (Fixture.away_team_id == away_team_id),
                (Fixture.home_team_id == away_team_id) & (Fixture.away_team_id == home_team_id),
            ),
        )
        .order_by(Fixture.kickoff_utc.desc())
    )
    if fixture.kickoff_utc is not None:
        stmt = stmt.where(
            Fixture.kickoff_utc >= cutoff,
            Fixture.kickoff_utc < fixture.kickoff_utc,
        )

    result = await db.execute(stmt)
    h2h_fixtures = result.scalars().all()

    reference_date = fixture.kickoff_utc or datetime.utcnow()

    # Weighted aggregation
    w_home_wins = 0.0
    w_draws = 0.0
    w_away_wins = 0.0
    w_total = 0.0
    w_goals_home = 0.0
    w_goals_away = 0.0
    w_btts = 0.0
    w_over_25 = 0.0

    for h in h2h_fixtures:
        if h.home_score is None or h.away_score is None:
            continue

        days_since = max(0.0, (reference_date - h.kickoff_utc).total_seconds() / 86400.0) if h.kickoff_utc else 365.0
        w = math.exp(-RECENCY_DECAY * days_since)

        # Normalise to home_team_id perspective
        if h.home_team_id == home_team_id:
            goals_for_home = h.home_score
            goals_for_away = h.away_score
        else:
            # Fixture was played with roles reversed
            goals_for_home = h.away_score
            goals_for_away = h.home_score

        total_goals = goals_for_home + goals_for_away

        if goals_for_home > goals_for_away:
            w_home_wins += w
        elif goals_for_home == goals_for_away:
            w_draws += w
        else:
            w_away_wins += w

        w_goals_home += goals_for_home * w
        w_goals_away += goals_for_away * w

        if goals_for_home >= 1 and goals_for_away >= 1:
            w_btts += w
        if total_goals > 2.5:
            w_over_25 += w

        w_total += w

    now = datetime.utcnow()

    if w_total <= 0 or len(h2h_fixtures) < MIN_MATCHES:
        # Fallback
        stmt = pg_insert(FixtureH2H).values(
            fixture_id=fixture_id,
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            h2h_matches_total=0,
            h2h_home_wins=0,
            h2h_draws=0,
            h2h_away_wins=0,
            h2h_avg_goals_home=0.0,
            h2h_avg_goals_away=0.0,
            h2h_avg_total_goals=0.0,
            h2h_btts_rate=0.0,
            h2h_over_25_rate=0.0,
            h2h_home_win_pct=0.0,
            h2h_draw_pct=0.0,
            h2h_away_win_pct=0.0,
            h2h_score=50.0,
            window_years=WINDOW_YEARS,
            computed_at=now,
            model_version=MODEL_VERSION,
        ).on_conflict_do_update(
            constraint="uq_fixture_h2h",
            set_={
                "home_team_id": home_team_id,
                "away_team_id": away_team_id,
                "h2h_matches_total": 0,
                "h2h_home_wins": 0,
                "h2h_draws": 0,
                "h2h_away_wins": 0,
                "h2h_avg_goals_home": 0.0,
                "h2h_avg_goals_away": 0.0,
                "h2h_avg_total_goals": 0.0,
                "h2h_btts_rate": 0.0,
                "h2h_over_25_rate": 0.0,
                "h2h_home_win_pct": 0.0,
                "h2h_draw_pct": 0.0,
                "h2h_away_win_pct": 0.0,
                "h2h_score": 50.0,
                "window_years": WINDOW_YEARS,
                "computed_at": now,
                "model_version": MODEL_VERSION,
            },
        )
        await db.execute(stmt)
        await db.commit()
        return {"fixture_id": fixture_id, "rows": 1, "h2h_matches": 0, "fallback": True}

    h2h_home_win_pct = w_home_wins / w_total
    h2h_draw_pct = w_draws / w_total
    h2h_away_win_pct = w_away_wins / w_total
    h2h_avg_goals_home = w_goals_home / w_total
    h2h_avg_goals_away = w_goals_away / w_total
    h2h_avg_total_goals = h2h_avg_goals_home + h2h_avg_goals_away
    h2h_btts_rate = w_btts / w_total
    h2h_over_25_rate = w_over_25 / w_total
    h2h_score = _clamp(h2h_home_win_pct * 100.0, 0.0, 100.0)

    # Count raw integers (unweighted) for informational fields
    raw_home_wins = sum(
        1 for h in h2h_fixtures
        if h.home_score is not None and h.away_score is not None and (
            (h.home_team_id == home_team_id and h.home_score > h.away_score) or
            (h.home_team_id == away_team_id and h.away_score > h.home_score)
        )
    )
    raw_draws = sum(
        1 for h in h2h_fixtures
        if h.home_score is not None and h.away_score is not None and h.home_score == h.away_score
    )
    raw_away_wins = sum(
        1 for h in h2h_fixtures
        if h.home_score is not None and h.away_score is not None and (
            (h.home_team_id == home_team_id and h.home_score < h.away_score) or
            (h.home_team_id == away_team_id and h.away_score < h.home_score)
        )
    )

    stmt = pg_insert(FixtureH2H).values(
        fixture_id=fixture_id,
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        h2h_matches_total=len(h2h_fixtures),
        h2h_home_wins=raw_home_wins,
        h2h_draws=raw_draws,
        h2h_away_wins=raw_away_wins,
        h2h_avg_goals_home=round(h2h_avg_goals_home, 4),
        h2h_avg_goals_away=round(h2h_avg_goals_away, 4),
        h2h_avg_total_goals=round(h2h_avg_total_goals, 4),
        h2h_btts_rate=round(h2h_btts_rate, 4),
        h2h_over_25_rate=round(h2h_over_25_rate, 4),
        h2h_home_win_pct=round(h2h_home_win_pct, 4),
        h2h_draw_pct=round(h2h_draw_pct, 4),
        h2h_away_win_pct=round(h2h_away_win_pct, 4),
        h2h_score=round(h2h_score, 2),
        window_years=WINDOW_YEARS,
        computed_at=now,
        model_version=MODEL_VERSION,
    ).on_conflict_do_update(
        constraint="uq_fixture_h2h",
        set_={
            "home_team_id": home_team_id,
            "away_team_id": away_team_id,
            "h2h_matches_total": len(h2h_fixtures),
            "h2h_home_wins": raw_home_wins,
            "h2h_draws": raw_draws,
            "h2h_away_wins": raw_away_wins,
            "h2h_avg_goals_home": round(h2h_avg_goals_home, 4),
            "h2h_avg_goals_away": round(h2h_avg_goals_away, 4),
            "h2h_avg_total_goals": round(h2h_avg_total_goals, 4),
            "h2h_btts_rate": round(h2h_btts_rate, 4),
            "h2h_over_25_rate": round(h2h_over_25_rate, 4),
            "h2h_home_win_pct": round(h2h_home_win_pct, 4),
            "h2h_draw_pct": round(h2h_draw_pct, 4),
            "h2h_away_win_pct": round(h2h_away_win_pct, 4),
            "h2h_score": round(h2h_score, 2),
            "window_years": WINDOW_YEARS,
            "computed_at": now,
            "model_version": MODEL_VERSION,
        },
    )
    await db.execute(stmt)
    await db.commit()
    return {"fixture_id": fixture_id, "rows": 1, "h2h_matches": len(h2h_fixtures)}


async def compute_h2h_for_league(
    db: AsyncSession,
    league_id: int,
    season_year: int,
) -> dict:
    fixtures_result = await db.execute(
        select(Fixture)
        .where(
            Fixture.league_id == league_id,
            Fixture.season_year == season_year,
        )
        .order_by(Fixture.kickoff_utc, Fixture.id)
    )
    fixtures = fixtures_result.scalars().all()

    if not fixtures:
        return {"league_id": league_id, "season_year": season_year, "fixtures": 0}

    computed = 0
    for fixture in fixtures:
        await compute_h2h_for_fixture(db, fixture.id)
        computed += 1

    return {
        "league_id": league_id,
        "season_year": season_year,
        "fixtures": computed,
    }
