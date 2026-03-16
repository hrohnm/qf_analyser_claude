from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fixture import Fixture
from app.models.fixture_events import FixtureEvent
from app.models.fixture_scoreline_distribution import FixtureScorelineDistribution
from app.models.fixture_top_scorer_pattern import FixtureTopScorerPattern

FINISHED_STATUSES = {"FT", "AET", "PEN"}
GOAL_DETAILS = {"Normal Goal", "Penalty"}
WINDOW_YEARS = 5
TOP_CANDIDATES = 5
MODEL_VERSION = "top_scorer_v1"
RECENCY_DECAY = 0.004
PENALTY_CONVERSION_BASE = 0.76


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _weight_for(reference_dt: datetime, fixture_dt: datetime | None) -> float:
    if fixture_dt is None:
        return 0.55
    days_since = max(0.0, (reference_dt - fixture_dt).total_seconds() / 86400.0)
    return math.exp(-RECENCY_DECAY * days_since)


def _team_key(team_id: int, player_id: int | None, player_name: str | None) -> tuple[int, str]:
    if player_id is not None:
        return team_id, f"id:{player_id}"
    return team_id, f"name:{(player_name or '').strip().lower()}"


def _empty_result(fixture: Fixture) -> dict:
    return {
        "fixture_id": fixture.id,
        "rows": 1,
        "top_scorer": None,
        "home_candidates": [],
        "away_candidates": [],
        "model_confidence": 0.0,
        "sample_size_home": 0,
        "sample_size_away": 0,
    }


async def compute_top_scorer_for_fixture(
    db: AsyncSession,
    fixture_id: int,
) -> dict:
    fixture = await db.get(Fixture, fixture_id)
    if fixture is None:
        return {"fixture_id": fixture_id, "rows": 0}

    reference_dt = fixture.kickoff_utc or datetime.utcnow()
    cutoff = reference_dt - timedelta(days=WINDOW_YEARS * 365)

    hist_result = await db.execute(
        select(Fixture)
        .where(
            Fixture.status_short.in_(FINISHED_STATUSES),
            Fixture.id != fixture.id,
            Fixture.kickoff_utc.is_not(None),
            Fixture.kickoff_utc >= cutoff,
            Fixture.kickoff_utc < reference_dt,
            or_(
                Fixture.home_team_id.in_([fixture.home_team_id, fixture.away_team_id]),
                Fixture.away_team_id.in_([fixture.home_team_id, fixture.away_team_id]),
            ),
        )
        .order_by(Fixture.kickoff_utc.desc(), Fixture.id.desc())
    )
    historical_fixtures = hist_result.scalars().all()

    if not historical_fixtures:
        payload = _empty_result(fixture)
        await _upsert_pattern(db, fixture, payload)
        return payload

    fixture_map = {row.id: row for row in historical_fixtures}
    fixture_ids = list(fixture_map.keys())

    events_result = await db.execute(
        select(FixtureEvent).where(FixtureEvent.fixture_id.in_(fixture_ids))
    )
    events = events_result.scalars().all()

    scoreline = (
        await db.execute(
            select(FixtureScorelineDistribution).where(FixtureScorelineDistribution.fixture_id == fixture.id)
        )
    ).scalar_one_or_none()

    team_fixture_counts: dict[int, set[int]] = defaultdict(set)
    for hist in historical_fixtures:
        if hist.home_team_id in {fixture.home_team_id, fixture.away_team_id}:
            team_fixture_counts[hist.home_team_id].add(hist.id)
        if hist.away_team_id in {fixture.home_team_id, fixture.away_team_id}:
            team_fixture_counts[hist.away_team_id].add(hist.id)

    player_data: dict[int, dict[tuple[int, str], dict]] = defaultdict(dict)
    team_weighted_goals: dict[int, float] = defaultdict(float)
    team_weighted_non_pen_goals: dict[int, float] = defaultdict(float)
    team_weighted_penalties: dict[int, float] = defaultdict(float)

    for event in events:
        hist_fixture = fixture_map.get(event.fixture_id)
        if hist_fixture is None or event.team_id not in {fixture.home_team_id, fixture.away_team_id}:
            continue

        weight = _weight_for(reference_dt, hist_fixture.kickoff_utc)
        detail = (event.detail or "").strip()

        if event.event_type == "Goal" and detail in GOAL_DETAILS:
            team_weighted_goals[event.team_id] += weight
            if detail == "Penalty":
                team_weighted_penalties[event.team_id] += weight
            else:
                team_weighted_non_pen_goals[event.team_id] += weight

            key = _team_key(event.team_id, event.player_id, event.player_name)
            entry = player_data[event.team_id].setdefault(
                key,
                {
                    "player_id": event.player_id,
                    "player_name": (event.player_name or "").strip() or f"Spieler {event.player_id}",
                    "team_id": event.team_id,
                    "total_goals": 0,
                    "penalty_goals": 0,
                    "non_penalty_goals": 0,
                    "weighted_goals": 0.0,
                    "weighted_penalty_goals": 0.0,
                    "weighted_non_penalty_goals": 0.0,
                    "last_goal_utc": None,
                },
            )
            entry["total_goals"] += 1
            entry["weighted_goals"] += weight
            if detail == "Penalty":
                entry["penalty_goals"] += 1
                entry["weighted_penalty_goals"] += weight
            else:
                entry["non_penalty_goals"] += 1
                entry["weighted_non_penalty_goals"] += weight
            if hist_fixture.kickoff_utc is not None:
                if entry["last_goal_utc"] is None or hist_fixture.kickoff_utc > entry["last_goal_utc"]:
                    entry["last_goal_utc"] = hist_fixture.kickoff_utc

        elif "Penalty" in detail:
            team_weighted_penalties[event.team_id] += weight * 0.5

    def build_candidates(team_id: int, team_lambda: float) -> tuple[list[dict], float, float, int]:
        matches = len(team_fixture_counts.get(team_id, set()))
        weighted_goals = team_weighted_goals.get(team_id, 0.0)
        weighted_non_pen = team_weighted_non_pen_goals.get(team_id, 0.0)
        weighted_penalties = team_weighted_penalties.get(team_id, 0.0)

        if matches == 0 or weighted_goals <= 0:
            return [], 0.0, 0.0, matches

        penalties_per_match = weighted_penalties / max(matches, 1)
        team_penalty_lambda = _clamp(
            penalties_per_match * PENALTY_CONVERSION_BASE,
            0.0,
            min(team_lambda * 0.4, 0.28),
        )
        open_play_lambda = max(team_lambda - team_penalty_lambda, 0.05)

        rows: list[dict] = []
        for entry in player_data.get(team_id, {}).values():
            weighted_goal_share = entry["weighted_goals"] / max(weighted_goals, 1e-6)
            weighted_non_pen_share = entry["weighted_non_penalty_goals"] / max(weighted_non_pen, 1e-6) if weighted_non_pen > 0 else weighted_goal_share
            penalty_share = entry["weighted_penalty_goals"] / max(weighted_penalties, 1e-6) if weighted_penalties > 0 else 0.0

            if entry["last_goal_utc"] is not None:
                days_since_goal = max(0.0, (reference_dt - entry["last_goal_utc"]).total_seconds() / 86400.0)
                recency_boost = _clamp(math.exp(-0.01 * days_since_goal), 0.65, 1.08)
            else:
                recency_boost = 0.8

            open_play_share = (
                0.65 * weighted_non_pen_share
                + 0.2 * weighted_goal_share
                + 0.15 * _clamp(entry["total_goals"] / max(matches, 1), 0.0, 0.45)
            )
            player_lambda = (
                open_play_lambda * open_play_share * recency_boost
                + team_penalty_lambda * penalty_share
            )
            anytime_probability = _clamp(1.0 - math.exp(-player_lambda), 0.0, 0.95)
            confidence = _clamp(
                0.3
                + 0.25 * min(matches / 10.0, 1.0)
                + 0.2 * min(entry["total_goals"] / 4.0, 1.0)
                + 0.15 * min(weighted_goals / 8.0, 1.0)
                + 0.1 * min(team_lambda / 1.6, 1.0),
                0.0,
                0.92,
            )

            rows.append(
                {
                    "player_id": entry["player_id"],
                    "player_name": entry["player_name"],
                    "team_id": team_id,
                    "goals_total": entry["total_goals"],
                    "penalty_goals": entry["penalty_goals"],
                    "weighted_goal_share": round(weighted_goal_share, 4),
                    "weighted_non_penalty_share": round(weighted_non_pen_share, 4),
                    "penalty_share": round(penalty_share, 4),
                    "team_penalties_per_match": round(penalties_per_match, 4),
                    "expected_lambda": round(player_lambda, 4),
                    "anytime_probability": round(anytime_probability, 4),
                    "confidence": round(confidence, 4),
                    "last_goal_utc": entry["last_goal_utc"].isoformat() if entry["last_goal_utc"] else None,
                }
            )

        rows.sort(
            key=lambda row: (
                row["anytime_probability"],
                row["confidence"],
                row["goals_total"],
                row["penalty_share"],
            ),
            reverse=True,
        )
        return rows[:TOP_CANDIDATES], penalties_per_match, weighted_penalties / max(weighted_goals, 1e-6), matches

    lambda_home = float(scoreline.lambda_home) if scoreline is not None else max((fixture.home_score or 0) * 0.6, 0.9)
    lambda_away = float(scoreline.lambda_away) if scoreline is not None else max((fixture.away_score or 0) * 0.6, 0.75)

    home_candidates, home_penalties_per_match, home_pen_conv_share, sample_home = build_candidates(fixture.home_team_id, lambda_home)
    away_candidates, away_penalties_per_match, away_pen_conv_share, sample_away = build_candidates(fixture.away_team_id, lambda_away)

    combined = sorted(home_candidates + away_candidates, key=lambda row: (row["anytime_probability"], row["confidence"]), reverse=True)
    top_scorer = combined[0] if combined else None
    model_confidence = _clamp(
        0.25
        + 0.2 * min(sample_home / 10.0, 1.0)
        + 0.2 * min(sample_away / 10.0, 1.0)
        + 0.15 * min(len(home_candidates) / 3.0, 1.0)
        + 0.15 * min(len(away_candidates) / 3.0, 1.0)
        + 0.05 * min(lambda_home / 1.5, 1.0)
        + 0.05 * min(lambda_away / 1.5, 1.0),
        0.0,
        0.93,
    )

    payload = {
        "fixture_id": fixture.id,
        "rows": 1,
        "top_scorer": top_scorer,
        "home_candidates": home_candidates,
        "away_candidates": away_candidates,
        "model_confidence": round(model_confidence, 4),
        "sample_size_home": sample_home,
        "sample_size_away": sample_away,
        "home_penalties_per_match": round(home_penalties_per_match, 4),
        "away_penalties_per_match": round(away_penalties_per_match, 4),
        "home_penalty_conversion_share": round(home_pen_conv_share, 4),
        "away_penalty_conversion_share": round(away_pen_conv_share, 4),
    }

    await _upsert_pattern(db, fixture, payload)
    return payload


async def _upsert_pattern(db: AsyncSession, fixture: Fixture, payload: dict) -> None:
    now = datetime.utcnow()
    stmt = pg_insert(FixtureTopScorerPattern).values(
        fixture_id=fixture.id,
        home_team_id=fixture.home_team_id,
        away_team_id=fixture.away_team_id,
        top_scorer=payload.get("top_scorer"),
        home_candidates=payload.get("home_candidates"),
        away_candidates=payload.get("away_candidates"),
        home_penalties_per_match=payload.get("home_penalties_per_match"),
        away_penalties_per_match=payload.get("away_penalties_per_match"),
        home_penalty_conversion_share=payload.get("home_penalty_conversion_share"),
        away_penalty_conversion_share=payload.get("away_penalty_conversion_share"),
        model_confidence=payload.get("model_confidence", 0.0),
        sample_size_home=payload.get("sample_size_home", 0),
        sample_size_away=payload.get("sample_size_away", 0),
        computed_at=now,
        model_version=MODEL_VERSION,
    ).on_conflict_do_update(
        constraint="uq_fixture_top_scorer_pattern",
        set_={
            "home_team_id": fixture.home_team_id,
            "away_team_id": fixture.away_team_id,
            "top_scorer": payload.get("top_scorer"),
            "home_candidates": payload.get("home_candidates"),
            "away_candidates": payload.get("away_candidates"),
            "home_penalties_per_match": payload.get("home_penalties_per_match"),
            "away_penalties_per_match": payload.get("away_penalties_per_match"),
            "home_penalty_conversion_share": payload.get("home_penalty_conversion_share"),
            "away_penalty_conversion_share": payload.get("away_penalty_conversion_share"),
            "model_confidence": payload.get("model_confidence", 0.0),
            "sample_size_home": payload.get("sample_size_home", 0),
            "sample_size_away": payload.get("sample_size_away", 0),
            "computed_at": now,
            "model_version": MODEL_VERSION,
        },
    )
    await db.execute(stmt)
    await db.commit()


async def compute_top_scorer_for_league(
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
        result = await compute_top_scorer_for_fixture(db, fixture.id)
        computed += int(result.get("rows", 0) > 0)

    return {
        "league_id": league_id,
        "season_year": season_year,
        "fixtures": len(fixtures),
        "computed": computed,
    }
