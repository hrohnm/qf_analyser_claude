from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fixture import Fixture
from app.models.fixture_events import FixtureEvent
from app.models.fixture_injury import FixtureInjury
from app.models.fixture_injury_impact import FixtureInjuryImpact

FINISHED_STATUSES = {"FT", "AET", "PEN"}
MODEL_VERSION = "injury_impact_v1"
WINDOW = 10

# Position weights for impact scoring.
# NOTE: fixture_injuries does not include position data; real positional data
# would come from the /fixtures/players endpoint. Until that data is available
# we apply a uniform fallback weight of 0.75 for all outfield players.
# Goalkeepers could be identified heuristically by player_name patterns if needed.
POSITION_WEIGHTS: dict[str, float] = {
    "goalkeeper": 1.0,
    "GK": 1.0,
}
DEFAULT_POSITION_WEIGHT = 0.75  # fallback for all players without known position


def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def _impact_bucket(score: float) -> str:
    if score < 20:
        return "gering"
    if score < 50:
        return "mittel"
    if score < 75:
        return "hoch"
    return "kritisch"


@dataclass
class _PlayerWindowStats:
    appearances: int
    early_events: int
    goals: int
    assists: int


async def _team_recent_fixtures(
    db: AsyncSession,
    team_id: int,
    season_year: int,
    league_id: int,
    before_kickoff: datetime | None,
) -> list[Fixture]:
    stmt = (
        select(Fixture)
        .where(
            Fixture.season_year == season_year,
            Fixture.league_id == league_id,
            Fixture.status_short.in_(FINISHED_STATUSES),
            (Fixture.home_team_id == team_id) | (Fixture.away_team_id == team_id),
        )
        .order_by(Fixture.kickoff_utc.desc())
        .limit(WINDOW)
    )
    if before_kickoff is not None:
        stmt = stmt.where(Fixture.kickoff_utc < before_kickoff)
    rows = await db.execute(stmt)
    return rows.scalars().all()


async def _event_rows_for_fixtures(db: AsyncSession, fixture_ids: list[int], team_id: int) -> list[FixtureEvent]:
    if not fixture_ids:
        return []
    rows = await db.execute(
        select(FixtureEvent).where(
            FixtureEvent.fixture_id.in_(fixture_ids),
            FixtureEvent.team_id == team_id,
        )
    )
    return rows.scalars().all()


def _player_window_stats(event_rows: list[FixtureEvent], player_id: int | None) -> _PlayerWindowStats:
    fixture_ids = set()
    early_events = 0
    goals = 0
    assists = 0
    for ev in event_rows:
        is_player = player_id is not None and ev.player_id == player_id
        is_assist = player_id is not None and ev.assist_id == player_id
        if not (is_player or is_assist):
            continue
        fixture_ids.add(ev.fixture_id)
        if is_player and ev.elapsed is not None and ev.elapsed <= 60:
            early_events += 1
        if is_player and ev.event_type == "Goal":
            goals += 1
        if is_assist:
            assists += 1
    return _PlayerWindowStats(
        appearances=len(fixture_ids),
        early_events=early_events,
        goals=goals,
        assists=assists,
    )


def _team_goal_total(fixtures: list[Fixture], team_id: int) -> int:
    total = 0
    for f in fixtures:
        if f.home_team_id == team_id and f.home_score is not None:
            total += f.home_score
        elif f.away_team_id == team_id and f.away_score is not None:
            total += f.away_score
    return total


def _replaceability_score(event_rows: list[FixtureEvent], player_id: int | None, team_goals: int) -> float:
    per_player: dict[int, dict[str, int | set[int]]] = {}
    for ev in event_rows:
        if ev.player_id is not None:
            slot = per_player.setdefault(ev.player_id, {"goals": 0, "assists": 0, "fixtures": set()})
            slot["fixtures"].add(ev.fixture_id)
            if ev.event_type == "Goal":
                slot["goals"] += 1
        if ev.assist_id is not None:
            slot = per_player.setdefault(ev.assist_id, {"goals": 0, "assists": 0, "fixtures": set()})
            slot["fixtures"].add(ev.fixture_id)
            slot["assists"] += 1

    alt_scores: list[float] = []
    for pid, stat in per_player.items():
        if player_id is not None and pid == player_id:
            continue
        goals = int(stat["goals"])
        assists = int(stat["assists"])
        if team_goals > 0:
            goal_rate = goals / team_goals
            assist_rate = assists / team_goals
            alt_scores.append(_clamp(0.6 * goal_rate + 0.4 * assist_rate, 0.0, 1.0))
    if not alt_scores:
        return 0.5

    alt_scores.sort(reverse=True)
    top = alt_scores[:3]
    avg = sum(top) / len(top)
    depth_factor = min(1.0, len(alt_scores) / 3.0)
    return _clamp(avg * depth_factor * 2.0, 0.0, 1.0)


def _position_weight(player_name: str | None) -> float:
    """Return a position-based weight for the player.

    Since fixture_injuries does not carry positional data, this is a heuristic.
    Goalkeepers tend to appear in rosters with 'GK' or 'Keeper' in their role
    annotation when available. Without position data we use the default weight.
    """
    if player_name:
        name_lower = player_name.lower()
        if any(kw in name_lower for kw in ("keeper", "goalkeeper")):
            return POSITION_WEIGHTS.get("goalkeeper", 1.0)
    return DEFAULT_POSITION_WEIGHT


def _availability_factor(injury_type: str | None) -> float:
    if injury_type == "Questionable":
        return 0.55
    return 1.0


def _confidence(player_id: int | None, fixtures_count: int, player_appearances: int) -> float:
    value = 1.0
    if player_id is None:
        value -= 0.3
    if fixtures_count < 5:
        value -= 0.2
    if player_appearances < 3:
        value -= 0.2
    if player_appearances == 0:
        value -= 0.2
    return _clamp(value, 0.1, 1.0)


async def recompute_fixture_injury_impacts(db: AsyncSession, fixture_id: int) -> dict:
    fixture = await db.get(Fixture, fixture_id)
    if not fixture:
        return {"fixture_id": fixture_id, "computed": 0}

    injuries_rows = await db.execute(
        select(FixtureInjury).where(FixtureInjury.fixture_id == fixture_id)
    )
    injuries = injuries_rows.scalars().all()

    await db.execute(
        FixtureInjuryImpact.__table__.delete().where(FixtureInjuryImpact.fixture_id == fixture_id)
    )

    if not injuries:
        await db.commit()
        return {"fixture_id": fixture_id, "computed": 0}

    inserted = 0
    for injury in injuries:
        if injury.team_id is None:
            continue

        team_fixtures = await _team_recent_fixtures(
            db=db,
            team_id=injury.team_id,
            season_year=fixture.season_year,
            league_id=fixture.league_id,
            before_kickoff=fixture.kickoff_utc,
        )
        fixture_ids = [f.id for f in team_fixtures]
        event_rows = await _event_rows_for_fixtures(db, fixture_ids, injury.team_id)

        player_stats = _player_window_stats(event_rows, injury.player_id)
        team_goals = max(1, _team_goal_total(team_fixtures, injury.team_id))

        fixtures_count = len(team_fixtures)
        appearance_rate = player_stats.appearances / max(1, fixtures_count)
        starter_proxy = 1.0 if player_stats.early_events >= max(1, player_stats.appearances // 2) else 0.6
        importance = _clamp(0.7 * appearance_rate + 0.3 * starter_proxy, 0.0, 1.0)

        goal_rate = player_stats.goals / team_goals
        assist_rate = player_stats.assists / team_goals
        contribution = _clamp(0.6 * goal_rate + 0.4 * assist_rate, 0.0, 1.0)
        if player_stats.appearances == 0:
            contribution = max(contribution, 0.25)

        replaceability = _replaceability_score(event_rows, injury.player_id, team_goals)
        availability = _availability_factor(injury.injury_type)
        pos_weight = _position_weight(injury.player_name)
        confidence = _confidence(injury.player_id, fixtures_count, player_stats.appearances)

        raw = (0.4 * importance) + (0.4 * contribution) + (0.2 * (1 - replaceability))
        impact_score = round(100.0 * raw * availability * pos_weight, 2)

        db.add(
            FixtureInjuryImpact(
                fixture_id=fixture_id,
                team_id=injury.team_id,
                player_id=injury.player_id,
                player_name=injury.player_name,
                impact_score=impact_score,
                impact_bucket=_impact_bucket(impact_score),
                importance_score=importance,
                contribution_score=contribution,
                replaceability_score=replaceability,
                availability_factor=availability,
                confidence=confidence,
                model_version=MODEL_VERSION,
                computed_at=datetime.utcnow(),
            )
        )
        inserted += 1

    await db.commit()
    return {"fixture_id": fixture_id, "computed": inserted}
