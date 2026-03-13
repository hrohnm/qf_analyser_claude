from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fixture import Fixture
from app.models.fixture_events import FixtureEvent
from app.models.team_goal_timing import TeamGoalTiming

FINISHED_STATUSES = {"FT", "AET", "PEN"}
MODEL_VERSION = "goal_timing_v1"

# Time windows: (label, min_elapsed_inclusive, max_elapsed_inclusive)
TIME_WINDOWS = [
    ("0_15", 0, 15),
    ("16_30", 16, 30),
    ("31_45", 31, 45),
    ("46_60", 46, 60),
    ("61_75", 61, 75),
    ("76_90", 76, 90),
]

GOAL_DETAILS = {"Normal Goal", "Penalty"}


def _window_for_elapsed(elapsed: int) -> str | None:
    for label, lo, hi in TIME_WINDOWS:
        if lo <= elapsed <= hi:
            return label
    # Goals in extra time (>90) count toward 76_90 window
    if elapsed > 90:
        return "76_90"
    return None


def _build_timing_dict(window_goals: dict[str, int], total_goals: int) -> dict:
    result = {}
    for label, _, _ in TIME_WINDOWS:
        goals = window_goals.get(label, 0)
        rate = goals / max(total_goals, 1)
        # index = (goals_in_window / total_goals) / (1/6) – normalised to uniform distribution
        index = rate / (1.0 / 6.0) if total_goals > 0 else 1.0
        result[label] = {
            "goals": goals,
            "rate": round(rate, 4),
            "index": round(index, 4),
        }
    return result


def _profil_typ(ht_attack_ratio: float) -> str:
    if ht_attack_ratio > 0.55:
        return "starte_stark"
    if ht_attack_ratio < 0.45:
        return "finisher"
    return "ausgeglichen"


async def compute_goal_timing_for_league(
    db: AsyncSession,
    league_id: int,
    season_year: int,
    extra_league_ids: list[int] | None = None,
) -> dict:
    all_league_ids = [league_id] + (extra_league_ids or [])
    # Load all finished fixtures for this league/season (+ companion leagues)
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

    fixture_ids = [f.id for f in fixtures]

    # Build fixture lookup: fixture_id -> Fixture
    fixture_map: dict[int, Fixture] = {f.id: f for f in fixtures}

    # Load all goal events for these fixtures (no own goals)
    events_result = await db.execute(
        select(FixtureEvent).where(
            FixtureEvent.fixture_id.in_(fixture_ids),
            FixtureEvent.event_type == "Goal",
            FixtureEvent.detail.in_(list(GOAL_DETAILS)),
        )
    )
    events = events_result.scalars().all()

    # Structure: team_id -> scope -> {"attack_windows": {label: count}, "defense_windows": {label: count},
    #                                  "goals_scored": int, "goals_conceded": int, "games": int}
    # scopes: "overall", "home", "away"
    team_data: dict[int, dict[str, dict]] = defaultdict(lambda: {
        "overall": {"attack_windows": defaultdict(int), "defense_windows": defaultdict(int),
                    "goals_scored": 0, "goals_conceded": 0, "games": set()},
        "home": {"attack_windows": defaultdict(int), "defense_windows": defaultdict(int),
                 "goals_scored": 0, "goals_conceded": 0, "games": set()},
        "away": {"attack_windows": defaultdict(int), "defense_windows": defaultdict(int),
                 "goals_scored": 0, "goals_conceded": 0, "games": set()},
    })

    # Track games per team to count games_played
    team_fixtures: dict[int, dict[str, set]] = defaultdict(lambda: {
        "overall": set(), "home": set(), "away": set()
    })

    # First pass: register all fixtures per team
    for f in fixtures:
        team_fixtures[f.home_team_id]["overall"].add(f.id)
        team_fixtures[f.home_team_id]["home"].add(f.id)
        team_fixtures[f.away_team_id]["overall"].add(f.id)
        team_fixtures[f.away_team_id]["away"].add(f.id)

    # Second pass: accumulate goal events
    for ev in events:
        if ev.elapsed is None:
            continue
        fixture = fixture_map.get(ev.fixture_id)
        if fixture is None:
            continue

        window = _window_for_elapsed(ev.elapsed)
        if window is None:
            continue

        scoring_team_id = ev.team_id
        if scoring_team_id == fixture.home_team_id:
            conceding_team_id = fixture.away_team_id
            scoring_scope = "home"
            conceding_scope = "away"
        else:
            conceding_team_id = fixture.home_team_id
            scoring_scope = "away"
            conceding_scope = "home"

        # Scoring team attack
        team_data[scoring_team_id]["overall"]["attack_windows"][window] += 1
        team_data[scoring_team_id]["overall"]["goals_scored"] += 1
        team_data[scoring_team_id][scoring_scope]["attack_windows"][window] += 1
        team_data[scoring_team_id][scoring_scope]["goals_scored"] += 1

        # Conceding team defense
        team_data[conceding_team_id]["overall"]["defense_windows"][window] += 1
        team_data[conceding_team_id]["overall"]["goals_conceded"] += 1
        team_data[conceding_team_id][conceding_scope]["defense_windows"][window] += 1
        team_data[conceding_team_id][conceding_scope]["goals_conceded"] += 1

    now = datetime.utcnow()
    rows_written = 0

    for team_id in team_fixtures:
        for scope in ("overall", "home", "away"):
            games_played = len(team_fixtures[team_id][scope])

            td = team_data[team_id][scope]
            goals_scored = td["goals_scored"]
            goals_conceded = td["goals_conceded"]
            attack_windows: dict[str, int] = dict(td["attack_windows"])
            defense_windows: dict[str, int] = dict(td["defense_windows"])

            timing_attack = _build_timing_dict(attack_windows, goals_scored)
            timing_defense = _build_timing_dict(defense_windows, goals_conceded)

            # First half goals: 0_15 + 16_30 + 31_45
            ht_goals = (
                attack_windows.get("0_15", 0)
                + attack_windows.get("16_30", 0)
                + attack_windows.get("31_45", 0)
            )
            ht_attack_ratio = ht_goals / max(goals_scored, 1)

            p_goal_first_30 = (
                (attack_windows.get("0_15", 0) + attack_windows.get("16_30", 0))
                / max(goals_scored, 1)
            )
            p_goal_last_15 = attack_windows.get("76_90", 0) / max(goals_scored, 1)

            profil = _profil_typ(ht_attack_ratio)

            stmt = pg_insert(TeamGoalTiming).values(
                team_id=team_id,
                league_id=league_id,
                season_year=season_year,
                scope=scope,
                games_played=games_played,
                goals_scored=goals_scored,
                goals_conceded=goals_conceded,
                timing_attack=timing_attack,
                timing_defense=timing_defense,
                ht_attack_ratio=round(ht_attack_ratio, 4),
                profil_typ=profil,
                p_goal_first_30=round(p_goal_first_30, 4),
                p_goal_last_15=round(p_goal_last_15, 4),
                computed_at=now,
                model_version=MODEL_VERSION,
            ).on_conflict_do_update(
                constraint="uq_team_goal_timing",
                set_={
                    "games_played": games_played,
                    "goals_scored": goals_scored,
                    "goals_conceded": goals_conceded,
                    "timing_attack": timing_attack,
                    "timing_defense": timing_defense,
                    "ht_attack_ratio": round(ht_attack_ratio, 4),
                    "profil_typ": profil,
                    "p_goal_first_30": round(p_goal_first_30, 4),
                    "p_goal_last_15": round(p_goal_last_15, 4),
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
        "teams": len(team_fixtures),
        "rows_written": rows_written,
    }
