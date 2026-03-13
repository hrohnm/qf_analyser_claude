from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fixture import Fixture
from app.models.team_home_advantage import TeamHomeAdvantage

FINISHED_STATUSES = {"FT", "AET", "PEN"}
MODEL_VERSION = "home_adv_v1"
MIN_GAMES = 3


def _points(gf: int, ga: int) -> int:
    if gf > ga:
        return 3
    if gf == ga:
        return 1
    return 0


def _tier(normalized_factor: float) -> str:
    if normalized_factor >= 1.4:
        return "fortress"
    if normalized_factor >= 1.1:
        return "home_strong"
    if normalized_factor >= 0.7:
        return "neutral"
    return "road_team"


async def compute_home_advantage_for_league(
    db: AsyncSession,
    league_id: int,
    season_year: int,
    extra_league_ids: list[int] | None = None,
) -> dict:
    all_league_ids = [league_id] + (extra_league_ids or [])
    fixtures_result = await db.execute(
        select(Fixture)
        .where(
            Fixture.league_id.in_(all_league_ids),
            Fixture.season_year == season_year,
            Fixture.status_short.in_(FINISHED_STATUSES),
        )
        .order_by(Fixture.kickoff_utc, Fixture.id)
    )
    fixtures = fixtures_result.scalars().all()

    if not fixtures:
        return {"league_id": league_id, "season_year": season_year, "teams": 0}

    # Accumulate home/away points per team
    # team_id -> {"home_pts": int, "home_games": int, "away_pts": int, "away_games": int}
    team_stats: dict[int, dict[str, int]] = defaultdict(
        lambda: {"home_pts": 0, "home_games": 0, "away_pts": 0, "away_games": 0}
    )

    for f in fixtures:
        if f.home_score is None or f.away_score is None:
            continue
        home_pts = _points(f.home_score, f.away_score)
        away_pts = _points(f.away_score, f.home_score)

        team_stats[f.home_team_id]["home_pts"] += home_pts
        team_stats[f.home_team_id]["home_games"] += 1
        team_stats[f.away_team_id]["away_pts"] += away_pts
        team_stats[f.away_team_id]["away_games"] += 1

    # First pass: compute advantage_factor for teams with sufficient data
    qualified: dict[int, dict[str, float]] = {}
    for team_id, stats in team_stats.items():
        if stats["home_games"] < MIN_GAMES or stats["away_games"] < MIN_GAMES:
            continue
        home_ppg = stats["home_pts"] / stats["home_games"]
        away_ppg = stats["away_pts"] / stats["away_games"]
        advantage_factor = home_ppg / max(away_ppg, 0.1)
        qualified[team_id] = {
            "home_ppg": home_ppg,
            "away_ppg": away_ppg,
            "advantage_factor": advantage_factor,
            "home_games": stats["home_games"],
            "away_games": stats["away_games"],
        }

    if not qualified:
        return {"league_id": league_id, "season_year": season_year, "teams": 0}

    # Compute league average advantage factor
    league_avg_factor = sum(v["advantage_factor"] for v in qualified.values()) / len(qualified)

    now = datetime.utcnow()
    rows_written = 0

    for team_id, vals in qualified.items():
        normalized_factor = vals["advantage_factor"] / max(league_avg_factor, 0.1)
        tier = _tier(normalized_factor)

        stmt = pg_insert(TeamHomeAdvantage).values(
            team_id=team_id,
            league_id=league_id,
            season_year=season_year,
            home_ppg=round(vals["home_ppg"], 4),
            away_ppg=round(vals["away_ppg"], 4),
            advantage_factor=round(vals["advantage_factor"], 4),
            league_avg_factor=round(league_avg_factor, 4),
            normalized_factor=round(normalized_factor, 4),
            games_home=vals["home_games"],
            games_away=vals["away_games"],
            tier=tier,
            computed_at=now,
            model_version=MODEL_VERSION,
        ).on_conflict_do_update(
            constraint="uq_team_home_advantage",
            set_={
                "home_ppg": round(vals["home_ppg"], 4),
                "away_ppg": round(vals["away_ppg"], 4),
                "advantage_factor": round(vals["advantage_factor"], 4),
                "league_avg_factor": round(league_avg_factor, 4),
                "normalized_factor": round(normalized_factor, 4),
                "games_home": vals["home_games"],
                "games_away": vals["away_games"],
                "tier": tier,
                "computed_at": now,
                "model_version": MODEL_VERSION,
            },
        )
        await db.execute(stmt)
        rows_written += 1

    await db.commit()
    return {
        "league_id": league_id,
        "season_year": season_year,
        "teams": rows_written,
        "league_avg_factor": round(league_avg_factor, 4),
    }
