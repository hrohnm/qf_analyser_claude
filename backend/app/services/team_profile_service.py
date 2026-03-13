"""
Team Season Profile service.

Aggregates per-team statistics for a league/season from fixture results and
fixture_statistics, producing:
  - Attack metrics (goals, xG, shots, conversion)
  - Defense metrics (conceded, clean sheets, xG against, shots against)
  - Style/intensity metrics (possession, passes, fouls, corners)
  - xG over/under-performance
  - Composite ratings (0-100) normalised within the league

One row per (team_id, league_id, season_year), upserted via ON CONFLICT.
"""
from __future__ import annotations

import math
import statistics
from collections import defaultdict
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fixture import Fixture
from app.models.fixture_statistics import FixtureStatistics
from app.models.team_season_profile import TeamSeasonProfile

FINISHED_STATUSES = {"FT", "AET", "PEN"}
MODEL_VERSION = "profile_v1"
MIN_GAMES = 3  # minimum finished matches to compute a profile


def _safe_avg(values: list[float | None]) -> float | None:
    valid = [v for v in values if v is not None]
    return round(sum(valid) / len(valid), 4) if valid else None


def _safe_ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return round(numerator / denominator, 4)


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _z_to_rating(z: float) -> float:
    """Convert z-score to 0-100 rating: 50 ± 15*z, clamped."""
    return round(_clamp(50.0 + 15.0 * z, 0.0, 100.0), 1)


def _compute_z_scores(values: list[float]) -> list[float]:
    """Return z-scores for a list of values. Returns zeros if no variance."""
    if len(values) < 2:
        return [0.0] * len(values)
    try:
        mean = statistics.mean(values)
        stdev = statistics.stdev(values)
    except statistics.StatisticsError:
        return [0.0] * len(values)
    if stdev < 1e-9:
        return [0.0] * len(values)
    return [(v - mean) / stdev for v in values]


async def compute_team_profiles_for_league(
    db: AsyncSession,
    league_id: int,
    season_year: int,
) -> dict:
    """
    Compute and upsert TeamSeasonProfile for every team in the league.
    Returns summary dict with computed/skipped counts.
    """
    # ── 1. Load all finished fixtures ────────────────────────────────────────
    fixtures_result = await db.execute(
        select(Fixture).where(
            Fixture.league_id == league_id,
            Fixture.season_year == season_year,
            Fixture.status_short.in_(FINISHED_STATUSES),
            Fixture.home_score.is_not(None),
            Fixture.away_score.is_not(None),
        )
    )
    fixtures = fixtures_result.scalars().all()

    if not fixtures:
        return {"league_id": league_id, "season_year": season_year, "computed": 0, "skipped": 0}

    fixture_ids = [f.id for f in fixtures]

    # ── 2. Load all fixture_statistics for those fixtures ────────────────────
    stats_result = await db.execute(
        select(FixtureStatistics).where(
            FixtureStatistics.fixture_id.in_(fixture_ids)
        )
    )
    all_stats = stats_result.scalars().all()

    # Index: (fixture_id, team_id) → FixtureStatistics
    stats_index: dict[tuple[int, int], FixtureStatistics] = {
        (s.fixture_id, s.team_id): s for s in all_stats
    }

    # ── 3. Aggregate raw data per team ───────────────────────────────────────
    # Buckets indexed by team_id
    raw: dict[int, dict] = defaultdict(lambda: {
        "games": 0,
        "goals_scored": 0,
        "goals_conceded": 0,
        "clean_sheets": 0,
        # per-game lists (None when stats missing for that fixture)
        "xg_for": [],
        "xg_against": [],
        "shots_total": [],
        "shots_on_target": [],
        "shots_inside_box": [],
        "shots_against": [],
        "shots_on_target_against": [],
        "gk_saves": [],
        "possession": [],
        "passes": [],
        "pass_accuracy": [],
        "corners": [],
        "fouls": [],
        "yellow_cards": [],
        "red_cards": [],
        "offsides": [],
    })

    for fix in fixtures:
        home_id = fix.home_team_id
        away_id = fix.away_team_id
        h_goals = int(fix.home_score)
        a_goals = int(fix.away_score)

        # Goals
        raw[home_id]["games"] += 1
        raw[home_id]["goals_scored"] += h_goals
        raw[home_id]["goals_conceded"] += a_goals
        if a_goals == 0:
            raw[home_id]["clean_sheets"] += 1

        raw[away_id]["games"] += 1
        raw[away_id]["goals_scored"] += a_goals
        raw[away_id]["goals_conceded"] += h_goals
        if h_goals == 0:
            raw[away_id]["clean_sheets"] += 1

        # Statistics per team
        home_stats = stats_index.get((fix.id, home_id))
        away_stats = stats_index.get((fix.id, away_id))

        def _f(s: FixtureStatistics | None, attr: str) -> float | None:
            if s is None:
                return None
            v = getattr(s, attr, None)
            return float(v) if v is not None else None

        # Home team attacking stats
        raw[home_id]["xg_for"].append(_f(home_stats, "expected_goals"))
        raw[home_id]["shots_total"].append(_f(home_stats, "shots_total"))
        raw[home_id]["shots_on_target"].append(_f(home_stats, "shots_on_goal"))
        raw[home_id]["shots_inside_box"].append(_f(home_stats, "shots_inside_box"))
        raw[home_id]["gk_saves"].append(_f(home_stats, "goalkeeper_saves"))
        raw[home_id]["possession"].append(_f(home_stats, "ball_possession"))
        raw[home_id]["passes"].append(_f(home_stats, "passes_total"))
        raw[home_id]["pass_accuracy"].append(_f(home_stats, "pass_accuracy"))
        raw[home_id]["corners"].append(_f(home_stats, "corner_kicks"))
        raw[home_id]["fouls"].append(_f(home_stats, "fouls"))
        raw[home_id]["yellow_cards"].append(_f(home_stats, "yellow_cards"))
        raw[home_id]["red_cards"].append(_f(home_stats, "red_cards"))
        raw[home_id]["offsides"].append(_f(home_stats, "offsides"))
        # Home team defensive: opponent's shots
        raw[home_id]["xg_against"].append(_f(away_stats, "expected_goals"))
        raw[home_id]["shots_against"].append(_f(away_stats, "shots_total"))
        raw[home_id]["shots_on_target_against"].append(_f(away_stats, "shots_on_goal"))

        # Away team attacking stats
        raw[away_id]["xg_for"].append(_f(away_stats, "expected_goals"))
        raw[away_id]["shots_total"].append(_f(away_stats, "shots_total"))
        raw[away_id]["shots_on_target"].append(_f(away_stats, "shots_on_goal"))
        raw[away_id]["shots_inside_box"].append(_f(away_stats, "shots_inside_box"))
        raw[away_id]["gk_saves"].append(_f(away_stats, "goalkeeper_saves"))
        raw[away_id]["possession"].append(_f(away_stats, "ball_possession"))
        raw[away_id]["passes"].append(_f(away_stats, "passes_total"))
        raw[away_id]["pass_accuracy"].append(_f(away_stats, "pass_accuracy"))
        raw[away_id]["corners"].append(_f(away_stats, "corner_kicks"))
        raw[away_id]["fouls"].append(_f(away_stats, "fouls"))
        raw[away_id]["yellow_cards"].append(_f(away_stats, "yellow_cards"))
        raw[away_id]["red_cards"].append(_f(away_stats, "red_cards"))
        raw[away_id]["offsides"].append(_f(away_stats, "offsides"))
        # Away team defensive: opponent's shots
        raw[away_id]["xg_against"].append(_f(home_stats, "expected_goals"))
        raw[away_id]["shots_against"].append(_f(home_stats, "shots_total"))
        raw[away_id]["shots_on_target_against"].append(_f(home_stats, "shots_on_goal"))

    # ── 4. Build per-team summary dicts ──────────────────────────────────────
    teams_eligible = {tid: d for tid, d in raw.items() if d["games"] >= MIN_GAMES}

    if not teams_eligible:
        return {"league_id": league_id, "season_year": season_year, "computed": 0, "skipped": len(raw)}

    summaries: dict[int, dict] = {}

    for team_id, d in teams_eligible.items():
        n = d["games"]
        gf = d["goals_scored"]
        ga = d["goals_conceded"]

        shots_pg = _safe_avg(d["shots_total"])
        sot_pg = _safe_avg(d["shots_on_target"])
        xg_for_pg = _safe_avg(d["xg_for"])
        xg_ag_pg = _safe_avg(d["xg_against"])

        xg_over = (
            round(gf / n - xg_for_pg, 3)
            if xg_for_pg is not None
            else None
        )
        xg_def = (
            round(xg_ag_pg - ga / n, 3)
            if xg_ag_pg is not None
            else None
        )

        summaries[team_id] = {
            "games_played": n,
            "goals_scored": gf,
            "goals_scored_pg": round(gf / n, 3),
            "goals_conceded": ga,
            "goals_conceded_pg": round(ga / n, 3),
            "clean_sheets": d["clean_sheets"],
            "clean_sheet_rate": round(d["clean_sheets"] / n, 3),
            "xg_for": round(sum(v for v in d["xg_for"] if v is not None), 3) if any(v is not None for v in d["xg_for"]) else None,
            "xg_for_pg": xg_for_pg,
            "xg_against": round(sum(v for v in d["xg_against"] if v is not None), 3) if any(v is not None for v in d["xg_against"]) else None,
            "xg_against_pg": xg_ag_pg,
            "shots_total_pg": shots_pg,
            "shots_on_target_pg": sot_pg,
            "shots_on_target_ratio": _safe_ratio(sot_pg, shots_pg),
            "shot_conversion_rate": _safe_ratio(gf / n if n else None, sot_pg),
            "shots_inside_box_pg": _safe_avg(d["shots_inside_box"]),
            "shots_against_pg": _safe_avg(d["shots_against"]),
            "shots_on_target_against_pg": _safe_avg(d["shots_on_target_against"]),
            "gk_saves_pg": _safe_avg(d["gk_saves"]),
            "possession_avg": _safe_avg(d["possession"]),
            "passes_pg": _safe_avg(d["passes"]),
            "pass_accuracy_avg": _safe_avg(d["pass_accuracy"]),
            "corners_pg": _safe_avg(d["corners"]),
            "fouls_pg": _safe_avg(d["fouls"]),
            "yellow_cards_pg": _safe_avg(d["yellow_cards"]),
            "red_cards_pg": _safe_avg(d["red_cards"]),
            "offsides_pg": _safe_avg(d["offsides"]),
            "xg_over_performance": xg_over,
            "xg_defense_performance": xg_def,
        }

    # ── 5. Compute composite ratings (league-normalised z-scores) ─────────────
    team_ids = list(summaries.keys())

    def _extract(key: str) -> list[float]:
        return [summaries[tid][key] or 0.0 for tid in team_ids]

    def _extract_opt(key: str) -> list[float] | None:
        vals = [summaries[tid][key] for tid in team_ids]
        if all(v is None for v in vals):
            return None
        return [v or 0.0 for v in vals]

    # Attack rating: goals_pg (35%), xg_for_pg (25%), sot_pg (20%), shot_conv (20%)
    gf_z = _compute_z_scores(_extract("goals_scored_pg"))
    sot_z_opt = _extract_opt("shots_on_target_pg")
    conv_z_opt = _extract_opt("shot_conversion_rate")
    xgf_z_opt = _extract_opt("xg_for_pg")

    sot_z = _compute_z_scores(sot_z_opt) if sot_z_opt else [0.0] * len(team_ids)
    conv_z = _compute_z_scores(conv_z_opt) if conv_z_opt else [0.0] * len(team_ids)
    xgf_z = _compute_z_scores(xgf_z_opt) if xgf_z_opt else [0.0] * len(team_ids)

    attack_z = [0.35 * gf_z[i] + 0.25 * xgf_z[i] + 0.20 * sot_z[i] + 0.20 * conv_z[i]
                for i in range(len(team_ids))]

    # Defense rating: -goals_conceded_pg (35%), -xg_against_pg (25%), clean_sheet_rate (25%), -sot_against_pg (15%)
    gc_z = _compute_z_scores(_extract("goals_conceded_pg"))
    cs_z = _compute_z_scores(_extract("clean_sheet_rate"))
    xga_z_opt = _extract_opt("xg_against_pg")
    sota_z_opt = _extract_opt("shots_on_target_against_pg")

    xga_z = _compute_z_scores(xga_z_opt) if xga_z_opt else [0.0] * len(team_ids)
    sota_z = _compute_z_scores(sota_z_opt) if sota_z_opt else [0.0] * len(team_ids)

    defense_z = [-0.35 * gc_z[i] - 0.25 * xga_z[i] + 0.25 * cs_z[i] - 0.15 * sota_z[i]
                 for i in range(len(team_ids))]

    # Intensity rating: possession (40%), pass_accuracy (35%), corners_pg (25%)
    poss_z_opt = _extract_opt("possession_avg")
    pacc_z_opt = _extract_opt("pass_accuracy_avg")
    corn_z_opt = _extract_opt("corners_pg")

    poss_z = _compute_z_scores(poss_z_opt) if poss_z_opt else [0.0] * len(team_ids)
    pacc_z = _compute_z_scores(pacc_z_opt) if pacc_z_opt else [0.0] * len(team_ids)
    corn_z = _compute_z_scores(corn_z_opt) if corn_z_opt else [0.0] * len(team_ids)

    intensity_z = [0.40 * poss_z[i] + 0.35 * pacc_z[i] + 0.25 * corn_z[i]
                   for i in range(len(team_ids))]

    for i, team_id in enumerate(team_ids):
        summaries[team_id]["attack_rating"] = _z_to_rating(attack_z[i])
        summaries[team_id]["defense_rating"] = _z_to_rating(defense_z[i])
        summaries[team_id]["intensity_rating"] = _z_to_rating(intensity_z[i])

    # ── 6. Upsert all rows ────────────────────────────────────────────────────
    now = datetime.utcnow()
    computed = 0

    for team_id, s in summaries.items():
        values = {
            "team_id": team_id,
            "league_id": league_id,
            "season_year": season_year,
            "computed_at": now,
            "model_version": MODEL_VERSION,
            **{k: v for k, v in s.items()},
        }
        stmt = (
            pg_insert(TeamSeasonProfile)
            .values(**values)
            .on_conflict_do_update(
                constraint="uq_team_season_profile",
                set_={k: v for k, v in values.items() if k not in ("team_id", "league_id", "season_year")},
            )
        )
        await db.execute(stmt)
        computed += 1

    await db.commit()

    skipped = len(raw) - len(summaries)
    return {
        "league_id": league_id,
        "season_year": season_year,
        "computed": computed,
        "skipped": skipped,
    }
