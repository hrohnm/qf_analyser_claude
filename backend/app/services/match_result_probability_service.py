from __future__ import annotations

import math
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fixture import Fixture
from app.models.fixture_goal_probability import FixtureGoalProbability
from app.models.fixture_injury_impact import FixtureInjuryImpact
from app.models.fixture_match_result_probability import FixtureMatchResultProbability
from app.models.fixture_scoreline_distribution import FixtureScorelineDistribution
from app.models.team_elo_snapshot import TeamEloSnapshot
from app.models.team_form_snapshot import TeamFormSnapshot
from app.models.team_season_profile import TeamSeasonProfile

# Phase-1 models - imported with graceful fallback if unavailable at runtime
try:
    from app.models.fixture_h2h import FixtureH2H
    _HAS_H2H = True
except ImportError:
    FixtureH2H = None  # type: ignore[assignment,misc]
    _HAS_H2H = False

try:
    from app.models.team_home_advantage import TeamHomeAdvantage
    _HAS_HOME_ADV = True
except ImportError:
    TeamHomeAdvantage = None  # type: ignore[assignment,misc]
    _HAS_HOME_ADV = False

MODEL_VERSION = "mrp_v3"
RECENT_MARKET_WINDOW = 12
RECENT_MARKET_SEASONS = 5

FALLBACK_1X2 = (0.45, 0.27, 0.28)  # home, draw, away
WEIGHTS = {
    "goal_prob": 0.35,
    "elo": 0.25,
    "form": 0.20,
    "h2h": 0.10,
    "home_adv": 0.05,
    "injury": 0.05,
}


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _normalise_1x2(home: float, draw: float, away: float) -> tuple[float, float, float]:
    total = home + draw + away
    if total <= 0:
        return FALLBACK_1X2
    return home / total, draw / total, away / total


def _elo_to_1x2(elo_home: float, elo_away: float) -> tuple[float, float, float]:
    # Reduced from 60 to 40: empirical analysis showed 60-pt advantage
    # over-weights home team, causing almost no draws/away wins to be predicted.
    home_adv = 40.0
    # Binary win probability from Elo (Bradley-Terry)
    p_home_bin = 1.0 / (1.0 + 10 ** ((elo_away - elo_home - home_adv) / 400.0))
    # Draw probability: peaks ~30% when evenly matched, falls off with Elo gap.
    # draw_scale=350 (was 280) gives slower decay so draw stays higher when
    # teams are close in quality — better matches empirical draw rate (~25%).
    eff_diff = abs(elo_home + home_adv - elo_away)
    p_draw = _clamp(0.30 * math.exp(-eff_diff / 350.0), 0.10, 0.38)
    # Remaining probability split by binary Elo odds
    p_remaining = 1.0 - p_draw
    p_home = p_home_bin * p_remaining
    p_away = (1.0 - p_home_bin) * p_remaining
    return _normalise_1x2(p_home, p_draw, p_away)


async def _elo_component(
    db: AsyncSession, fixture: Fixture
) -> tuple[tuple[float, float, float], bool]:
    """Returns ((p_home, p_draw, p_away), has_data)."""
    rows = await db.execute(
        select(TeamEloSnapshot).where(
            TeamEloSnapshot.league_id == fixture.league_id,
            TeamEloSnapshot.season_year == fixture.season_year,
            TeamEloSnapshot.team_id.in_([fixture.home_team_id, fixture.away_team_id]),
        )
    )
    elo_rows = {r.team_id: r for r in rows.scalars().all()}

    if fixture.home_team_id not in elo_rows or fixture.away_team_id not in elo_rows:
        return FALLBACK_1X2, False

    elo_home = float(elo_rows[fixture.home_team_id].elo_overall)
    elo_away = float(elo_rows[fixture.away_team_id].elo_overall)
    return _elo_to_1x2(elo_home, elo_away), True


async def _form_component(
    db: AsyncSession, fixture: Fixture
) -> tuple[tuple[float, float, float], float, float, bool]:
    """Returns ((p_home, p_draw, p_away), form_home_score, form_away_score, has_data)."""
    rows = await db.execute(
        select(TeamFormSnapshot).where(
            TeamFormSnapshot.league_id == fixture.league_id,
            TeamFormSnapshot.season_year == fixture.season_year,
            TeamFormSnapshot.team_id.in_([fixture.home_team_id, fixture.away_team_id]),
            TeamFormSnapshot.scope.in_(["home", "away"]),
        )
    )
    form_rows = rows.scalars().all()

    form_home: float | None = None
    form_away: float | None = None

    for row in form_rows:
        if row.team_id == fixture.home_team_id and row.scope == "home":
            form_home = float(row.form_score)
        elif row.team_id == fixture.away_team_id and row.scope == "away":
            form_away = float(row.form_score)

    if form_home is None or form_away is None:
        # Try overall scope as fallback
        rows2 = await db.execute(
            select(TeamFormSnapshot).where(
                TeamFormSnapshot.league_id == fixture.league_id,
                TeamFormSnapshot.season_year == fixture.season_year,
                TeamFormSnapshot.team_id.in_([fixture.home_team_id, fixture.away_team_id]),
                TeamFormSnapshot.scope == "overall",
            )
        )
        for row in rows2.scalars().all():
            if row.team_id == fixture.home_team_id and form_home is None:
                form_home = float(row.form_score)
            elif row.team_id == fixture.away_team_id and form_away is None:
                form_away = float(row.form_score)

    if form_home is None or form_away is None:
        return FALLBACK_1X2, 0.0, 0.0, False

    form_ratio = form_home / max(form_away, 1.0)
    p_home_bin = _clamp(form_ratio / (form_ratio + 1.0), 0.2, 0.8)
    # Draw probability: higher when form is balanced (ratio near 1.0).
    # imbalance=0 → equal form, imbalance→1 → total mismatch.
    imbalance = abs(form_ratio - 1.0) / (form_ratio + 1.0)
    p_form_draw = _clamp(0.30 * (1.0 - imbalance), 0.10, 0.35)
    p_remaining = 1.0 - p_form_draw
    probs = _normalise_1x2(p_home_bin * p_remaining, p_form_draw, (1.0 - p_home_bin) * p_remaining)
    return probs, form_home, form_away, True


async def _goal_prob_component(
    db: AsyncSession, fixture_id: int
) -> tuple[tuple[float, float, float], float, float, float, float, float, float, float, float, bool]:
    """Returns (1x2, p_btts, p_over_15, p_over_25, p_over_35, p_home_cs, p_away_cs, has_data)."""
    # Try scoreline distribution first
    sd_row = await db.get(FixtureScorelineDistribution, fixture_id)
    if sd_row is None:
        # Try by fixture_id via select
        res = await db.execute(
            select(FixtureScorelineDistribution).where(
                FixtureScorelineDistribution.fixture_id == fixture_id
            )
        )
        sd_row = res.scalar_one_or_none()

    if sd_row is not None:
        probs = _normalise_1x2(
            float(sd_row.p_home_win), float(sd_row.p_draw), float(sd_row.p_away_win)
        )
        return (
            probs,
            float(sd_row.p_btts),
            float(sd_row.p_over_15),
            float(sd_row.p_over_25),
            float(sd_row.p_over_35),
            float(sd_row.p_home_clean_sheet),
            float(sd_row.p_away_clean_sheet),
            True,
        )

    # Fallback: compute from lambdas inline (import locally to avoid circular)
    from app.services.scoreline_service import (
        FALLBACK_LAMBDA_AWAY,
        FALLBACK_LAMBDA_HOME,
        _compute_matrix,
        _derive_market_probs,
        _get_lambdas,
    )

    # We need a db session, but _get_lambdas needs fixture_id
    gp_rows = await db.execute(
        select(FixtureGoalProbability).where(FixtureGoalProbability.fixture_id == fixture_id)
    )
    goal_probs = gp_rows.scalars().all()
    lambda_home = FALLBACK_LAMBDA_HOME
    lambda_away = FALLBACK_LAMBDA_AWAY
    for gp in goal_probs:
        if gp.is_home:
            lambda_home = float(gp.lambda_weighted)
        else:
            lambda_away = float(gp.lambda_weighted)

    matrix = _compute_matrix(lambda_home, lambda_away)
    mp = _derive_market_probs(matrix)
    probs = _normalise_1x2(mp["p_home_win"], mp["p_draw"], mp["p_away_win"])

    has_data = bool(goal_probs)
    return (
        probs,
        mp["p_btts"],
        mp["p_over_15"],
        mp["p_over_25"],
        mp["p_over_35"],
        mp["p_home_clean_sheet"],
        mp["p_away_clean_sheet"],
        has_data,
    )


async def _h2h_component(
    db: AsyncSession, fixture_id: int
) -> tuple[tuple[float, float, float], float | None, float | None, float | None, int, bool]:
    """Returns ((p_home, p_draw, p_away), h2h_home_pct, h2h_btts, h2h_over25, matches, has_data)."""
    if not _HAS_H2H:
        return FALLBACK_1X2, None, None, None, 0, False

    res = await db.execute(
        select(FixtureH2H).where(FixtureH2H.fixture_id == fixture_id)
    )
    h2h = res.scalar_one_or_none()

    if h2h is None or h2h.h2h_matches_total == 0:
        return FALLBACK_1X2, None, None, None, 0, False

    probs = _normalise_1x2(
        float(h2h.h2h_home_win_pct),
        float(h2h.h2h_draw_pct),
        float(h2h.h2h_away_win_pct),
    )
    return (
        probs,
        float(h2h.h2h_home_win_pct),
        float(h2h.h2h_btts_rate),
        float(h2h.h2h_over_25_rate),
        int(h2h.h2h_matches_total),
        True,
    )


async def _recent_market_rates_component(
    db: AsyncSession,
    fixture: Fixture,
) -> tuple[float | None, float | None, bool]:
    """Estimate BTTS / Over 2.5 from recent fixture-only team rates."""

    async def _team_rates(team_id: int, target_is_home: bool) -> tuple[dict[str, float], bool]:
        result = await db.execute(
            select(Fixture).where(
                Fixture.league_id == fixture.league_id,
                Fixture.season_year >= fixture.season_year - (RECENT_MARKET_SEASONS - 1),
                Fixture.season_year <= fixture.season_year,
                Fixture.status_short.in_(["FT", "AET", "PEN"]),
                ((Fixture.home_team_id == team_id) | (Fixture.away_team_id == team_id)),
                Fixture.kickoff_utc < fixture.kickoff_utc if fixture.kickoff_utc is not None else True,
            ).order_by(Fixture.kickoff_utc.desc(), Fixture.id.desc()).limit(RECENT_MARKET_WINDOW)
        )
        matches = result.scalars().all()
        if not matches:
            return {}, False

        scores_w = 0.0
        concedes_w = 0.0
        btts_w = 0.0
        over25_w = 0.0
        total_w = 0.0

        for idx, m in enumerate(matches):
            if m.home_score is None or m.away_score is None:
                continue
            is_home = m.home_team_id == team_id
            gf = m.home_score if is_home else m.away_score
            ga = m.away_score if is_home else m.home_score
            base_w = math.exp(-0.10 * idx)
            venue_w = 1.15 if is_home == target_is_home else 0.9
            w = base_w * venue_w

            scores_w += (1.0 if gf > 0 else 0.0) * w
            concedes_w += (1.0 if ga > 0 else 0.0) * w
            btts_w += (1.0 if gf > 0 and ga > 0 else 0.0) * w
            over25_w += (1.0 if (gf + ga) > 2 else 0.0) * w
            total_w += w

        if total_w <= 0:
            return {}, False

        return {
            "scores_rate": scores_w / total_w,
            "concedes_rate": concedes_w / total_w,
            "btts_rate": btts_w / total_w,
            "over25_rate": over25_w / total_w,
            "matches": float(len(matches)),
        }, True

    home_rates, has_home = await _team_rates(fixture.home_team_id, True)
    away_rates, has_away = await _team_rates(fixture.away_team_id, False)
    if not has_home or not has_away:
        return None, None, False

    p_home_scores_recent = (home_rates["scores_rate"] + away_rates["concedes_rate"]) / 2.0
    p_away_scores_recent = (away_rates["scores_rate"] + home_rates["concedes_rate"]) / 2.0
    p_btts_recent = _clamp(
        0.7 * (p_home_scores_recent * p_away_scores_recent)
        + 0.3 * ((home_rates["btts_rate"] + away_rates["btts_rate"]) / 2.0),
        0.02,
        0.98,
    )
    p_over25_recent = _clamp(
        (home_rates["over25_rate"] + away_rates["over25_rate"]) / 2.0,
        0.02,
        0.98,
    )
    return p_btts_recent, p_over25_recent, True


async def _profile_market_component(
    db: AsyncSession,
    fixture: Fixture,
) -> tuple[float | None, bool]:
    """BTTS estimate from season scoring/conceding and clean-sheet profiles."""
    rows = await db.execute(
        select(TeamSeasonProfile).where(
            TeamSeasonProfile.league_id == fixture.league_id,
            TeamSeasonProfile.season_year == fixture.season_year,
            TeamSeasonProfile.team_id.in_([fixture.home_team_id, fixture.away_team_id]),
        )
    )
    profiles = {row.team_id: row for row in rows.scalars().all()}
    home = profiles.get(fixture.home_team_id)
    away = profiles.get(fixture.away_team_id)
    if home is None or away is None:
        return None, False

    home_scores = _clamp(
        0.45
        + 0.18 * (float(home.goals_scored_pg) - 1.2)
        + 0.10 * (float(away.goals_conceded_pg) - 1.2)
        - 0.15 * float(away.clean_sheet_rate),
        0.05,
        0.95,
    )
    away_scores = _clamp(
        0.43
        + 0.18 * (float(away.goals_scored_pg) - 1.1)
        + 0.10 * (float(home.goals_conceded_pg) - 1.1)
        - 0.15 * float(home.clean_sheet_rate),
        0.05,
        0.95,
    )

    profile_btts = _clamp(
        (home_scores * away_scores) * 0.8
        + 0.2 * (
            (1.0 - float(home.clean_sheet_rate)) * (1.0 - float(away.clean_sheet_rate))
        ),
        0.02,
        0.98,
    )
    return profile_btts, True


def _blend_market_probability(
    baseline: float,
    recent: float | None,
    h2h_rate: float | None,
    h2h_matches: int,
    recent_has_data: bool,
    recent_weight: float,
    h2h_weight: float,
) -> float:
    weight_sum = 1.0
    blended = baseline

    if recent_has_data and recent is not None:
        blended += recent * recent_weight
        weight_sum += recent_weight

    if h2h_rate is not None and h2h_matches > 0:
        effective_h2h_weight = h2h_weight * min(1.0, h2h_matches / 5.0)
        blended += h2h_rate * effective_h2h_weight
        weight_sum += effective_h2h_weight

    return _clamp(blended / weight_sum, 0.01, 0.99)


async def _home_adv_component(
    db: AsyncSession, fixture: Fixture, base_home: float, base_draw: float, base_away: float
) -> tuple[tuple[float, float, float], float | None, bool]:
    """Apply home advantage factor to 1X2 probs. Returns adjusted probs, factor, has_data."""
    if not _HAS_HOME_ADV:
        return _normalise_1x2(base_home, base_draw, base_away), None, False

    res = await db.execute(
        select(TeamHomeAdvantage).where(
            TeamHomeAdvantage.team_id == fixture.home_team_id,
            TeamHomeAdvantage.league_id == fixture.league_id,
            TeamHomeAdvantage.season_year == fixture.season_year,
        )
    )
    ha = res.scalar_one_or_none()

    if ha is None:
        return _normalise_1x2(base_home, base_draw, base_away), None, False

    factor = float(ha.normalized_factor)
    p_home, p_draw, p_away = base_home, base_draw, base_away

    if factor >= 1.4:  # fortress
        p_home *= 1.05
    elif factor <= 0.7:  # road team
        p_away *= 1.05

    return _normalise_1x2(p_home, p_draw, p_away), factor, True


async def _injury_component(
    db: AsyncSession, fixture: Fixture, base_home: float, base_draw: float, base_away: float
) -> tuple[tuple[float, float, float], float | None, bool]:
    """Apply injury delta to 1X2 probs. Returns adjusted probs, delta, has_data."""
    res = await db.execute(
        select(FixtureInjuryImpact).where(
            FixtureInjuryImpact.fixture_id == fixture.id
        )
    )
    impact_rows = res.scalars().all()

    if not impact_rows:
        return _normalise_1x2(base_home, base_draw, base_away), None, False

    home_impact = sum(
        float(r.impact_score) for r in impact_rows if r.team_id == fixture.home_team_id
    )
    away_impact = sum(
        float(r.impact_score) for r in impact_rows if r.team_id == fixture.away_team_id
    )

    # positive delta = home advantage from opponent injuries
    injury_delta = (away_impact - home_impact) / 100.0
    p_home = base_home * (1.0 + injury_delta * 0.1)
    return _normalise_1x2(p_home, base_draw, base_away), round(injury_delta, 4), True


async def compute_match_result_for_fixture(db: AsyncSession, fixture_id: int) -> dict:
    """Compute and upsert combined match result probability for a single fixture."""
    fixture = await db.get(Fixture, fixture_id)
    if fixture is None:
        return {"fixture_id": fixture_id, "rows": 0, "error": "fixture not found"}

    confidence = 1.0

    # 1. Elo component
    elo_probs, has_elo = await _elo_component(db, fixture)
    if not has_elo:
        confidence -= 0.15

    # 2. Form component
    form_probs, form_home_score, form_away_score, has_form = await _form_component(db, fixture)
    if not has_form:
        confidence -= 0.15

    # 3. Goal probability component
    (
        goal_prob_probs,
        p_btts,
        p_over_15,
        p_over_25,
        p_over_35,
        p_home_cs,
        p_away_cs,
        has_goal_prob,
    ) = await _goal_prob_component(db, fixture_id)
    if not has_goal_prob:
        confidence -= 0.10

    # 4. H2H component
    h2h_probs, h2h_home_pct, h2h_btts_rate, h2h_over25_rate, h2h_matches, has_h2h = await _h2h_component(db, fixture_id)
    if not has_h2h:
        confidence -= 0.10

    recent_btts, recent_over25, has_recent_markets = await _recent_market_rates_component(db, fixture)
    if not has_recent_markets:
        confidence -= 0.05
    profile_btts, has_profile_markets = await _profile_market_component(db, fixture)
    if not has_profile_markets:
        confidence -= 0.03

    # 5. Home advantage component (applied to base combination without injury)
    # Build weighted base first (without home_adv and injury)
    base_home = (
        WEIGHTS["goal_prob"] * goal_prob_probs[0]
        + WEIGHTS["elo"] * elo_probs[0]
        + WEIGHTS["form"] * form_probs[0]
        + WEIGHTS["h2h"] * h2h_probs[0]
    )
    base_draw = (
        WEIGHTS["goal_prob"] * goal_prob_probs[1]
        + WEIGHTS["elo"] * elo_probs[1]
        + WEIGHTS["form"] * form_probs[1]
        + WEIGHTS["h2h"] * h2h_probs[1]
    )
    base_away = (
        WEIGHTS["goal_prob"] * goal_prob_probs[2]
        + WEIGHTS["elo"] * elo_probs[2]
        + WEIGHTS["form"] * form_probs[2]
        + WEIGHTS["h2h"] * h2h_probs[2]
    )

    ha_probs, home_adv_factor, has_home_adv = await _home_adv_component(
        db, fixture, base_home, base_draw, base_away
    )

    # 6. Injury component
    inj_probs, injury_delta, has_injury = await _injury_component(
        db, fixture, base_home, base_draw, base_away
    )

    # Dynamic weight redistribution: when a component has no real data (uses
    # FALLBACK_1X2), redistribute its weight to goal_prob and form proportionally.
    # This prevents the biased fallback (0.45/0.27/0.28) from polluting the result.
    w_goal_prob = WEIGHTS["goal_prob"]
    w_elo = WEIGHTS["elo"]
    w_form = WEIGHTS["form"]
    w_h2h = WEIGHTS["h2h"]
    w_home_adv = WEIGHTS["home_adv"]
    w_injury = WEIGHTS["injury"]

    if not has_h2h:
        # Redistribute H2H weight: 60% to goal_prob, 40% to form
        w_goal_prob += w_h2h * 0.60
        w_form += w_h2h * 0.40
        w_h2h = 0.0
    if not has_injury:
        # Redistribute injury weight: 60% to goal_prob, 40% to form
        w_goal_prob += w_injury * 0.60
        w_form += w_injury * 0.40
        w_injury = 0.0

    # Final combination: weighted sum of all components
    final_home = (
        w_goal_prob * goal_prob_probs[0]
        + w_elo * elo_probs[0]
        + w_form * form_probs[0]
        + w_h2h * h2h_probs[0]
        + w_home_adv * ha_probs[0]
        + w_injury * inj_probs[0]
    )
    final_draw = (
        w_goal_prob * goal_prob_probs[1]
        + w_elo * elo_probs[1]
        + w_form * form_probs[1]
        + w_h2h * h2h_probs[1]
        + w_home_adv * ha_probs[1]
        + w_injury * inj_probs[1]
    )
    final_away = (
        w_goal_prob * goal_prob_probs[2]
        + w_elo * elo_probs[2]
        + w_form * form_probs[2]
        + w_h2h * h2h_probs[2]
        + w_home_adv * ha_probs[2]
        + w_injury * inj_probs[2]
    )

    p_home_win, p_draw, p_away_win = _normalise_1x2(final_home, final_draw, final_away)
    p_btts = _blend_market_probability(
        baseline=p_btts,
        recent=(
            _clamp(
                (
                    (recent_btts if recent_btts is not None else p_btts)
                    + (profile_btts if profile_btts is not None else p_btts)
                ) / (
                    (1 if recent_btts is not None else 0)
                    + (1 if profile_btts is not None else 0)
                ),
                0.01,
                0.99,
            )
            if (recent_btts is not None or profile_btts is not None)
            else None
        ),
        h2h_rate=h2h_btts_rate,
        h2h_matches=h2h_matches,
        recent_has_data=has_recent_markets or has_profile_markets,
        recent_weight=0.70,
        h2h_weight=0.25,
    )
    p_over_25 = _blend_market_probability(
        baseline=p_over_25,
        recent=recent_over25,
        h2h_rate=h2h_over25_rate,
        h2h_matches=h2h_matches,
        recent_has_data=has_recent_markets,
        recent_weight=0.70,
        h2h_weight=0.30,
    )
    confidence = max(0.3, confidence)

    now = datetime.utcnow()
    values = dict(
        fixture_id=fixture_id,
        p_home_win=round(p_home_win, 4),
        p_draw=round(p_draw, 4),
        p_away_win=round(p_away_win, 4),
        p_btts=round(p_btts, 4),
        p_over_25=round(p_over_25, 4),
        p_over_15=round(p_over_15, 4),
        p_over_35=round(p_over_35, 4),
        p_home_clean_sheet=round(p_home_cs, 4),
        p_away_clean_sheet=round(p_away_cs, 4),
        src_goal_prob_weight=WEIGHTS["goal_prob"],
        src_elo_weight=WEIGHTS["elo"],
        src_form_weight=WEIGHTS["form"],
        src_h2h_weight=WEIGHTS["h2h"],
        src_home_adv_weight=WEIGHTS["home_adv"],
        src_injury_weight=WEIGHTS["injury"],
        elo_home_prob=round(elo_probs[0], 4),
        elo_draw_prob=round(elo_probs[1], 4),
        elo_away_prob=round(elo_probs[2], 4),
        form_home_score=round(form_home_score, 4),
        form_away_score=round(form_away_score, 4),
        h2h_home_pct=round(h2h_home_pct, 4) if h2h_home_pct is not None else None,
        home_adv_factor=round(home_adv_factor, 4) if home_adv_factor is not None else None,
        injury_delta=round(injury_delta, 4) if injury_delta is not None else None,
        confidence=round(confidence, 4),
        computed_at=now,
        model_version=MODEL_VERSION,
    )

    stmt = pg_insert(FixtureMatchResultProbability).values(**values).on_conflict_do_update(
        constraint="uq_fixture_match_result_probability",
        set_={k: v for k, v in values.items() if k != "fixture_id"},
    )
    await db.execute(stmt)
    await db.commit()

    return {
        "fixture_id": fixture_id,
        "rows": 1,
        "p_home_win": round(p_home_win, 4),
        "p_draw": round(p_draw, 4),
        "p_away_win": round(p_away_win, 4),
        "confidence": round(confidence, 4),
    }


async def compute_match_result_for_league(db: AsyncSession, league_id: int, season_year: int) -> dict:
    """Compute and upsert match result probabilities for all fixtures in a league/season."""
    result = await db.execute(
        select(Fixture).where(
            Fixture.league_id == league_id,
            Fixture.season_year == season_year,
        )
    )
    fixtures = result.scalars().all()

    if not fixtures:
        return {"league_id": league_id, "season_year": season_year, "computed": 0}

    computed = 0
    errors = 0
    for fixture in fixtures:
        try:
            res = await compute_match_result_for_fixture(db, fixture.id)
            if res.get("rows", 0) > 0:
                computed += 1
        except Exception:
            errors += 1

    return {
        "league_id": league_id,
        "season_year": season_year,
        "computed": computed,
        "errors": errors,
    }
