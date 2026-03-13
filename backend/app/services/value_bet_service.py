from __future__ import annotations

from datetime import datetime
from typing import Callable

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fixture import Fixture
from app.models.fixture_match_result_probability import FixtureMatchResultProbability
from app.models.fixture_odds import FixtureOdds
from app.models.fixture_value_bet import FixtureValueBet

MODEL_VERSION = "value_bet_v1"
BETANO_BOOKMAKER_ID = 32

# Maps bet_id -> {bet_value_label -> callable(mrp) -> model_prob}
MARKET_MAPPING: dict[int, dict[str, Callable]] = {
    1: {  # Match Winner
        "Home": lambda mrp: mrp.p_home_win,
        "Draw": lambda mrp: mrp.p_draw,
        "Away": lambda mrp: mrp.p_away_win,
    },
    5: {  # Goals O/U
        "Over 2.5": lambda mrp: mrp.p_over_25,
        "Under 2.5": lambda mrp: 1.0 - mrp.p_over_25,
        "Over 1.5": lambda mrp: mrp.p_over_15,
        "Under 1.5": lambda mrp: 1.0 - mrp.p_over_15,
    },
    26: {  # BTTS
        "Yes": lambda mrp: mrp.p_btts,
        "No": lambda mrp: 1.0 - mrp.p_btts,
    },
    12: {  # Double Chance
        "Home/Draw": lambda mrp: mrp.p_home_win + mrp.p_draw,
        "Home/Away": lambda mrp: mrp.p_home_win + mrp.p_away_win,
        "Draw/Away": lambda mrp: mrp.p_draw + mrp.p_away_win,
    },
}

MARKET_NAMES: dict[int, str] = {
    1: "Match Winner",
    5: "Goals O/U",
    26: "Both Teams Score",
    12: "Double Chance",
}


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _tier(edge: float, model_prob: float) -> str:
    if edge > 0.08 and model_prob > 0.1:
        return "strong_value"
    if edge > 0.04 and model_prob > 0.1:
        return "value"
    if edge > 0.01:
        return "marginal"
    return "no_value"


def _estimate_vig(odds_values: list[dict], market_mapping: dict[str, Callable]) -> float:
    """Estimate vig as 1 - sum(1/odd) for all known outcomes in the market."""
    inv_sum = 0.0
    count = 0
    for entry in odds_values:
        label = entry.get("value", "")
        if label in market_mapping:
            try:
                odd = float(entry.get("odd", 0.0))
                if odd > 1.0:
                    inv_sum += 1.0 / odd
                    count += 1
            except (TypeError, ValueError):
                pass
    if count == 0:
        return 0.0
    return round(max(0.0, 1.0 - inv_sum), 4)


def _compute_value_bet(
    fixture_id: int,
    bet_id: int,
    market_name: str,
    bet_value: str,
    bookmaker_odd: float,
    model_prob: float,
    vig: float,
) -> dict | None:
    if bookmaker_odd <= 1.0 or model_prob <= 0.0:
        return None

    implied_prob = 1.0 / bookmaker_odd
    edge = model_prob - implied_prob
    expected_value = model_prob * (bookmaker_odd - 1.0) - (1.0 - model_prob)
    kelly_fraction = max(0.0, edge / (bookmaker_odd - 1.0)) * 0.25
    fair_odd = 1.0 / max(model_prob, 0.01)
    tier = _tier(edge, model_prob)

    return {
        "fixture_id": fixture_id,
        "market_name": market_name,
        "bet_value": bet_value,
        "bet_id": bet_id,
        "model_prob": round(model_prob, 4),
        "bookmaker_odd": round(bookmaker_odd, 4),
        "implied_prob": round(implied_prob, 4),
        "vig": vig,
        "fair_odd": round(fair_odd, 4),
        "edge": round(edge, 4),
        "expected_value": round(expected_value, 4),
        "kelly_fraction": round(kelly_fraction, 4),
        "tier": tier,
    }


async def compute_value_bets_for_fixture(db: AsyncSession, fixture_id: int) -> dict:
    """Compute and upsert value bets for a single fixture."""
    # Load MRP
    res = await db.execute(
        select(FixtureMatchResultProbability).where(
            FixtureMatchResultProbability.fixture_id == fixture_id
        )
    )
    mrp = res.scalar_one_or_none()
    if mrp is None:
        return {"fixture_id": fixture_id, "rows": 0, "error": "no match result probability found"}

    # Load Betano odds
    odds_res = await db.execute(
        select(FixtureOdds).where(
            FixtureOdds.fixture_id == fixture_id,
            FixtureOdds.bookmaker_id == BETANO_BOOKMAKER_ID,
        )
    )
    odds_rows = odds_res.scalars().all()
    if not odds_rows:
        return {"fixture_id": fixture_id, "rows": 0, "error": "no Betano odds found"}

    # Index odds by bet_id
    odds_by_bet_id: dict[int, FixtureOdds] = {}
    for row in odds_rows:
        odds_by_bet_id[row.bet_id] = row

    now = datetime.utcnow()
    inserted = 0
    skipped = 0

    for bet_id, value_map in MARKET_MAPPING.items():
        if bet_id not in odds_by_bet_id:
            continue

        odds_row = odds_by_bet_id[bet_id]
        odds_values: list[dict] = odds_row.values or []
        market_name = MARKET_NAMES.get(bet_id, odds_row.bet_name)
        vig = _estimate_vig(odds_values, value_map)

        # Build lookup: bet_value_label -> odd
        odd_by_label: dict[str, float] = {}
        for entry in odds_values:
            label = entry.get("value", "")
            try:
                odd = float(entry.get("odd", 0.0))
                if odd > 1.0:
                    odd_by_label[label] = odd
            except (TypeError, ValueError):
                pass

        for bet_value, prob_fn in value_map.items():
            if bet_value not in odd_by_label:
                continue

            bookmaker_odd = odd_by_label[bet_value]
            model_prob = float(prob_fn(mrp))
            model_prob = _clamp(model_prob, 0.0, 1.0)

            vb = _compute_value_bet(
                fixture_id=fixture_id,
                bet_id=bet_id,
                market_name=market_name,
                bet_value=bet_value,
                bookmaker_odd=bookmaker_odd,
                model_prob=model_prob,
                vig=vig,
            )
            if vb is None:
                skipped += 1
                continue

            # Filter out obviously wrong markets
            if vb["edge"] <= -0.15:
                skipped += 1
                continue

            row_values = {**vb, "computed_at": now, "model_version": MODEL_VERSION}
            stmt = pg_insert(FixtureValueBet).values(**row_values).on_conflict_do_update(
                constraint="uq_fixture_value_bet",
                set_={
                    k: v
                    for k, v in row_values.items()
                    if k not in ("fixture_id", "market_name", "bet_value")
                },
            )
            await db.execute(stmt)
            inserted += 1

    await db.commit()
    return {"fixture_id": fixture_id, "rows": inserted, "skipped": skipped}


async def compute_value_bets_for_league(db: AsyncSession, league_id: int, season_year: int) -> dict:
    """Compute and upsert value bets for all fixtures in a league/season."""
    result = await db.execute(
        select(Fixture).where(
            Fixture.league_id == league_id,
            Fixture.season_year == season_year,
        )
    )
    fixtures = result.scalars().all()

    if not fixtures:
        return {"league_id": league_id, "season_year": season_year, "computed": 0}

    total_bets = 0
    fixtures_with_bets = 0
    errors = 0

    for fixture in fixtures:
        try:
            res = await compute_value_bets_for_fixture(db, fixture.id)
            if res.get("rows", 0) > 0:
                fixtures_with_bets += 1
                total_bets += res["rows"]
        except Exception:
            errors += 1

    return {
        "league_id": league_id,
        "season_year": season_year,
        "fixtures_processed": len(fixtures),
        "fixtures_with_bets": fixtures_with_bets,
        "total_bets": total_bets,
        "errors": errors,
    }
