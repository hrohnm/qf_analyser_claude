"""
Pattern-based betting slip generator — no AI, pure model data.

Generates 6 deterministic slips from today's MRP + goal probability patterns:

  Slip 1 – DC + Trifft (Betbuilder)
  Slip 2 – Siegerschein (Home/Away outright, incl. away favourites)
  Slip 3 – Tore Über 1,5 (reines O1.5, p ≥72%, Zielquote 4–6.5x)
  Slip 4 – DC Kombi (pure Double Chance, dc_prob ≥75%, Zielquote 8–12x)
  Slip 5 – Verdoppler Ü1,5 (Over 1.5 Tore, Zielquote ~2.0)
  Slip 6 – Vierer U4,5 (Under 4.5 Tore, genau 4 Picks)

Target combined odds: 8–12 per slip (Slips 1–4), ~2.0 (Slip 5), variabel (Slip 6).
Optional league_ids filter restricts to specific competitions.
"""
from __future__ import annotations

import logging
from datetime import datetime, date
from typing import Any

from sqlalchemy import cast, Date, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.day_betting_slip import DayBettingSlip
from app.models.fixture import Fixture
from app.models.fixture_goal_probability import FixtureGoalProbability
from app.models.fixture_match_result_probability import FixtureMatchResultProbability
from app.models.fixture_scoreline_distribution import FixtureScorelineDistribution
from app.models.league import League
from app.models.team import Team

logger = logging.getLogger(__name__)
MODEL_VERSION = "pattern_v1"
SOURCE = "pattern"
BETBUILDER_DISCOUNT = 0.87

TARGET_LO, TARGET_HI = 8.0, 12.0
MITTEL_LO,  MITTEL_HI  = 4.0,  6.5   # for goal-over slips — 4 picks at 75% = 32% win rate
VERDOPPLER_LO, VERDOPPLER_HI = 1.80, 2.20


# ─── helpers ─────────────────────────────────────────────────────────────────

def _fair(p: float) -> float:
    """1 / probability, clamped to sane range."""
    if p <= 0:
        return 99.0
    return round(1.0 / p, 4)


def _combined(odds: list[float]) -> float:
    r = 1.0
    for o in odds:
        r *= o
    return round(r, 3)


def _pick_for_target(
    candidates: list[dict],
    target_lo: float = TARGET_LO,
    target_hi: float = TARGET_HI,
) -> tuple[list[dict], float]:
    """
    Greedily select picks from sorted (highest prob first) candidates until
    combined odds fall in [target_lo, target_hi].

    Overshooting by up to 20 % is accepted on the last pick.
    """
    selected: list[dict] = []
    combined = 1.0
    for c in candidates:
        new = combined * c["fair_odd"]
        if new > target_hi * 1.20:
            continue  # skip — would push too high
        selected.append(c)
        combined = new
        if combined >= target_lo:
            break  # reached target
    return selected, round(combined, 3)


# ─── data loader ─────────────────────────────────────────────────────────────

async def _load_fixtures_with_probs(
    db: AsyncSession,
    target_date: date,
    league_ids: list[int] | None = None,
) -> list[dict]:
    """Return all fixtures for the day enriched with MRP + goal prob data."""
    is_past = target_date < date.today()
    q = (
        select(Fixture)
        .where(cast(Fixture.kickoff_utc, Date) == target_date)
    )
    if not is_past:
        now_utc = datetime.utcnow()
        q = q.where(
            Fixture.status_short.in_({"NS", "TBD", "PST"}),
            Fixture.kickoff_utc > now_utc,
        )
    if league_ids:
        q = q.where(Fixture.league_id.in_(league_ids))
    fixtures = (await db.execute(q.order_by(Fixture.kickoff_utc))).scalars().all()

    if not fixtures:
        return []

    fixture_ids = [f.id for f in fixtures]
    team_ids = list({f.home_team_id for f in fixtures} | {f.away_team_id for f in fixtures})
    league_ids = list({f.league_id for f in fixtures})
    season_years = list({f.season_year for f in fixtures})

    teams = {t.id: t for t in (await db.execute(
        select(Team).where(Team.id.in_(team_ids))
    )).scalars().all()}
    leagues = {l.id: l for l in (await db.execute(
        select(League).where(League.id.in_(league_ids))
    )).scalars().all()}

    mrp_rows = (await db.execute(
        select(FixtureMatchResultProbability)
        .where(FixtureMatchResultProbability.fixture_id.in_(fixture_ids))
    )).scalars().all()
    mrp_map = {r.fixture_id: r for r in mrp_rows}

    gp_rows = (await db.execute(
        select(FixtureGoalProbability)
        .where(FixtureGoalProbability.fixture_id.in_(fixture_ids))
    )).scalars().all()
    gp_map: dict[tuple[int, int], FixtureGoalProbability] = {}
    for gp in gp_rows:
        gp_map[(gp.fixture_id, gp.team_id)] = gp

    sd_rows = (await db.execute(
        select(FixtureScorelineDistribution)
        .where(FixtureScorelineDistribution.fixture_id.in_(fixture_ids))
    )).scalars().all()
    sd_map = {r.fixture_id: r for r in sd_rows}

    result = []
    for fix in fixtures:
        mrp = mrp_map.get(fix.id)
        if mrp is None:
            continue  # no MRP → skip
        gp_home = gp_map.get((fix.id, fix.home_team_id))
        gp_away = gp_map.get((fix.id, fix.away_team_id))
        sd = sd_map.get(fix.id)
        league = leagues.get(fix.league_id)
        home_team = teams.get(fix.home_team_id)
        away_team = teams.get(fix.away_team_id)

        # p_under_45: sum scoreline probabilities where total goals <= 4
        p_under_45: float | None = None
        if sd and sd.p_matrix:
            p_under_45 = round(sum(
                v for k, v in sd.p_matrix.items()
                if sum(int(x) for x in k.split("_")) <= 4
            ), 4)

        result.append({
            "fixture_id": fix.id,
            "home": home_team.name if home_team else f"T{fix.home_team_id}",
            "away": away_team.name if away_team else f"T{fix.away_team_id}",
            "league": (league.name if league else "?")[:24],
            "country": (league.country if league else "")[:20],
            "kickoff": fix.kickoff_utc.strftime("%H:%M") if fix.kickoff_utc else "?",
            # MRP
            "p_home": float(mrp.p_home_win),
            "p_draw": float(mrp.p_draw),
            "p_away": float(mrp.p_away_win),
            "p_over_15": float(mrp.p_over_15) if mrp.p_over_15 else None,
            "p_over_25": float(mrp.p_over_25),
            "p_btts": float(mrp.p_btts),
            "confidence": float(mrp.confidence),
            # Goal probability per team
            "p_home_scores": float(gp_home.p_ge_1_goal) if gp_home else None,
            "p_away_scores": float(gp_away.p_ge_1_goal) if gp_away else None,
            # Scoreline-derived
            "p_under_45": p_under_45,
        })
    return result


# ─── Slip 1: DC + Trifft ─────────────────────────────────────────────────────

def _build_slip1(fixtures: list[dict]) -> tuple[list[dict], float]:
    """Betbuilder pairs: best DC + team scores, sorted by pair probability."""
    candidates: list[dict] = []

    for fix in fixtures:
        # Best DC option
        dc_opts = [
            ("1X", fix["p_home"] + fix["p_draw"]),
            ("X2", fix["p_draw"] + fix["p_away"]),
            ("12", fix["p_home"] + fix["p_away"]),
        ]
        dc_label, dc_prob = max(dc_opts, key=lambda x: x[1])

        # Best scoring team for the BB second leg
        ps_home = fix.get("p_home_scores")
        ps_away = fix.get("p_away_scores")
        if ps_home is None and ps_away is None:
            continue

        if ps_home is not None and ps_away is not None:
            if ps_home >= ps_away:
                team_label = "Heim trifft"
                team_prob = ps_home
                bet_id = 16
            else:
                team_label = "Auswärts trifft"
                team_prob = ps_away
                bet_id = 17
        elif ps_home is not None:
            team_label = "Heim trifft"
            team_prob = ps_home
            bet_id = 16
        else:
            team_label = "Auswärts trifft"
            team_prob = ps_away  # type: ignore
            bet_id = 17

        if team_prob < 0.70:
            continue  # team unlikely to score → skip

        pair_prob = dc_prob * team_prob * BETBUILDER_DISCOUNT
        pair_fair = _fair(pair_prob)
        if pair_fair < 1.10 or pair_fair > 2.50:
            continue  # outside useful range

        candidates.append({
            "pair_prob": pair_prob,
            "fair_odd": pair_fair,
            "dc_label": dc_label,
            "dc_prob": dc_prob,
            "team_label": team_label,
            "team_prob": team_prob,
            "bet_id_team": bet_id,
            **fix,
        })

    candidates.sort(key=lambda c: c["pair_prob"], reverse=True)
    selected, combined = _pick_for_target(candidates)

    picks: list[dict] = []
    for c in selected:
        dc_odd = round(_fair(c["dc_prob"]), 2)
        team_odd = round(_fair(c["team_prob"]), 2)
        picks.append({
            "fixture_id": c["fixture_id"],
            "home": c["home"], "away": c["away"],
            "league": c["league"], "kickoff": c["kickoff"],
            "market": "Doppelchance",
            "pick": c["dc_label"],
            "bet_id": 12, "bet_value": c["dc_label"],
            "odd": dc_odd,
            "betbuilder": False,
            "reasoning": f"DC {c['dc_label']} ({c['dc_prob']*100:.0f}%)",
            "result": None,
        })
        picks.append({
            "fixture_id": c["fixture_id"],
            "home": c["home"], "away": c["away"],
            "league": c["league"], "kickoff": c["kickoff"],
            "market": c["team_label"],
            "pick": "Ja",
            "bet_id": c["bet_id_team"], "bet_value": "Over 0.5",
            "odd": team_odd,
            "betbuilder": True,
            "reasoning": f"{c['team_label']} ({c['team_prob']*100:.0f}%)",
            "result": None,
        })

    return picks, combined


# ─── Slip 2: Siegerschein ─────────────────────────────────────────────────────

def _build_slip2(fixtures: list[dict]) -> tuple[list[dict], float]:
    """
    Outright wins (Home or Away, no draw).

    Thresholds:
      Home win  : p_home >= 0.55  (clear home favourite)
      Away win  : p_away >= 0.52  (away favourite is a strong signal even at lower %)
    Upper cap   : 0.85  (above that fair odds < 1.18 → boring)

    Sort order: ascending probability = highest fair odds first.
    This lets the greedy _pick_for_target reach 8–12 in 4–6 picks instead of
    requiring 8+ low-odds picks.
    """
    candidates: list[dict] = []

    for fix in fixtures:
        p_h, p_a = fix["p_home"], fix["p_away"]

        # Away favourite
        if p_a > p_h and p_a >= 0.52:
            winner_prob = p_a
            pick_label = "Auswärtssieg"
            bet_value = "Away"
            is_away_fav = True
        elif p_h >= 0.55:
            winner_prob = p_h
            pick_label = "Heimsieg"
            bet_value = "Home"
            is_away_fav = False
        else:
            continue

        if winner_prob > 0.85:
            continue  # too safe, fair odds < 1.18

        fair = _fair(winner_prob)
        candidates.append({
            "fair_odd": fair,
            "winner_prob": winner_prob,
            "pick_label": pick_label,
            "bet_value": bet_value,
            "is_away_fav": is_away_fav,
            **fix,
        })

    # Sort ascending by probability (= descending by fair odds) so the greedy
    # selector picks the highest-odds candidates first and hits 8–12 faster.
    # Tie-break: prefer away favourites at the same probability level.
    candidates.sort(key=lambda c: (c["winner_prob"], not c["is_away_fav"]))
    selected, combined = _pick_for_target(candidates)

    picks = []
    for c in selected:
        away_tag = " (Auswärtsfavorit)" if c["is_away_fav"] else ""
        picks.append({
            "fixture_id": c["fixture_id"],
            "home": c["home"], "away": c["away"],
            "league": c["league"], "kickoff": c["kickoff"],
            "market": "Siegerwette",
            "pick": c["pick_label"],
            "bet_id": 1, "bet_value": c["bet_value"],
            "odd": round(c["fair_odd"], 2),
            "betbuilder": False,
            "reasoning": f"{c['pick_label']}{away_tag} ({c['winner_prob']*100:.0f}%)",
            "result": None,
        })

    return picks, combined


# ─── Slip 3: Tore Über 1,5 ───────────────────────────────────────────────────

def _build_slip3(fixtures: list[dict]) -> tuple[list[dict], float]:
    """
    Rein Über-1,5-Tore Kombi. Kein O2.5 mehr.
    Schwelle: p_over_15 >= 0.72 (74% Einzeltrefferquote im Backtest).
    Zielquote: 4–6.5x (MITTEL) → 4–5 Picks, ~22–32% Slipgewinnwahrsch.
    Sortierung: höchste Wahrscheinlichkeit zuerst.
    """
    candidates: list[dict] = []

    for fix in fixtures:
        p15 = fix.get("p_over_15")
        if p15 is None or p15 < 0.72 or p15 > 0.95:
            continue
        fair = _fair(p15)
        if fair < 1.05:
            continue
        candidates.append({
            "fair_odd": fair,
            "prob": p15,
            "market": "Über 1,5 Tore",
            "bet_value": "Over 1.5",
            "bet_id": 5,
            **fix,
        })

    candidates.sort(key=lambda c: -c["prob"])
    selected, combined = _pick_for_target(candidates, MITTEL_LO, MITTEL_HI)

    picks = []
    for c in selected:
        picks.append({
            "fixture_id": c["fixture_id"],
            "home": c["home"], "away": c["away"],
            "league": c["league"], "kickoff": c["kickoff"],
            "market": c["market"],
            "pick": c["bet_value"],
            "bet_id": c["bet_id"], "bet_value": c["bet_value"],
            "odd": round(c["fair_odd"], 2),
            "betbuilder": False,
            "reasoning": f"{c['market']} ({c['prob']*100:.0f}%)",
            "result": None,
        })

    return picks, combined


# ─── Slip 4: DC Kombi ────────────────────────────────────────────────────────

def _build_slip4(fixtures: list[dict]) -> tuple[list[dict], float]:
    """
    Pure Double Chance parlay — replaces BTTS (which had only 55% pick rate).

    DC picks have a real-world accuracy of ~78% vs BTTS at 55%.
    At 4 picks: DC 0.78^4 ≈ 37% win prob vs BTTS 0.55^4 ≈ 9%.

    Filter: take the best DC option per game only if dc_prob >= 0.75.
    Sort: safest first (highest probability = most reliable picks first).
    """
    candidates: list[dict] = []

    for fix in fixtures:
        dc_opts = [
            ("1X",   fix["p_home"] + fix["p_draw"]),
            ("X2",   fix["p_draw"] + fix["p_away"]),
            ("Home/Away", fix["p_home"] + fix["p_away"]),
        ]
        dc_label, dc_prob = max(dc_opts, key=lambda x: x[1])

        if dc_prob < 0.75:
            continue  # too uncertain for a pure DC parlay

        fair = _fair(dc_prob)
        if fair < 1.05:
            continue

        bet_value = {"1X": "Home/Draw", "X2": "Draw/Away", "Home/Away": "Home/Away"}.get(dc_label, dc_label)
        candidates.append({
            "fair_odd": fair,
            "dc_prob": dc_prob,
            "dc_label": dc_label,
            "bet_value": bet_value,
            **fix,
        })

    # Safest first → higher combined probability
    candidates.sort(key=lambda c: -c["dc_prob"])
    selected, combined = _pick_for_target(candidates)

    picks = []
    for c in selected:
        picks.append({
            "fixture_id": c["fixture_id"],
            "home": c["home"], "away": c["away"],
            "league": c["league"], "kickoff": c["kickoff"],
            "market": "Doppelchance",
            "pick": c["dc_label"],
            "bet_id": 12, "bet_value": c["bet_value"],
            "odd": round(c["fair_odd"], 2),
            "betbuilder": False,
            "reasoning": f"DC {c['dc_label']} ({c['dc_prob']*100:.0f}%)",
            "result": None,
        })

    return picks, combined


# ─── Slip 5: deaktiviert ─────────────────────────────────────────────────────

def _build_slip5(fixtures: list[dict]) -> tuple[list[dict], float]:
    """Verdoppler Ü1,5 deaktiviert — ersetzt durch Slip 3 (Tore Über 1,5)."""
    return [], 0.0


# ─── Slip 6: Verdoppler U4,5 ────────────────────────────────────────────────

def _build_slip6(fixtures: list[dict]) -> tuple[list[dict], float]:
    """
    Sicherer Vierer-Kombischein aus dem Markt Unter 4,5 Tore.

    p_under_45 wird aus der Scoreline-Distribution berechnet (Summe aller
    Ergebnisse mit ≤ 4 Gesamttoren).

    Filter  : p_under_45 in [0.65, 0.95]
    Sort    : aufsteigend nach p_under_45 (höchste faire Quote zuerst)
    Ergebnis: genau 4 Picks (mind. 4 Kandidaten nötig, sonst leer)
    """
    candidates: list[dict] = []

    for fix in fixtures:
        p = fix.get("p_under_45")
        if p is None or p < 0.65 or p > 0.95:
            continue
        fair = _fair(p)
        if fair < 1.05:
            continue
        candidates.append({"fair_odd": fair, "prob": p, **fix})

    # Lowest p first = highest fair odds first
    candidates.sort(key=lambda c: c["prob"])
    selected = candidates[:4]
    if len(selected) < 4:
        return [], 0.0
    combined = _combined([c["fair_odd"] for c in selected])

    picks = []
    for c in selected:
        picks.append({
            "fixture_id": c["fixture_id"],
            "home": c["home"], "away": c["away"],
            "league": c["league"], "kickoff": c["kickoff"],
            "market": "Unter 4,5 Tore",
            "pick": "Under 4.5",
            "bet_id": 5, "bet_value": "Under 4.5",
            "odd": round(c["fair_odd"], 2),
            "betbuilder": False,
            "reasoning": f"U4,5 ({c['prob']*100:.0f}%)",
            "result": None,
        })

    return picks, combined


# ─── Single-slip regeneration ────────────────────────────────────────────────

_SLIP_BUILDERS = {
    1: _build_slip1,
    2: _build_slip2,
    3: _build_slip3,
    4: _build_slip4,
    6: _build_slip6,
}


async def regenerate_single_slip(
    db: AsyncSession,
    target_date: date,
    slip_nr: int,
) -> dict:
    """Re-runs one slip builder and hot-swaps it in the stored day JSON."""
    if slip_nr not in _SLIP_BUILDERS:
        raise ValueError(f"Unbekannte slip_nr: {slip_nr}")

    existing = (await db.execute(
        select(DayBettingSlip).where(
            DayBettingSlip.slip_date == target_date,
            DayBettingSlip.source == SOURCE,
        )
    )).scalar_one_or_none()
    if not existing:
        raise ValueError(f"Keine Pattern-Scheine für {target_date}")

    fixtures = await _load_fixtures_with_probs(db, target_date)
    if not fixtures:
        raise ValueError(f"Keine Spiele mit MRP-Daten am {target_date}")

    picks, combined = _SLIP_BUILDERS[slip_nr](fixtures)
    name = SLIP_NAMES[slip_nr]
    n_games = len({p["fixture_id"] for p in picks if not p.get("betbuilder")})
    new_slip = {
        "slip_nr": slip_nr, "name": name,
        "combined_odd": combined, "n_games": n_games,
        "reasoning": f"{name} – {n_games} Spiele · faire Kombinationsquote {combined:.2f}",
        "picks": picks,
    }

    full_data = dict(existing.slips)
    slips = [s for s in full_data.get("slips", []) if s.get("slip_nr") != slip_nr]
    if picks:  # only include if new slip has picks
        slips.append(new_slip)
        slips.sort(key=lambda s: s["slip_nr"])
    full_data["slips"] = slips

    now = datetime.utcnow()
    stmt = pg_insert(DayBettingSlip).values(
        slip_date=target_date,
        source=SOURCE,
        slips=full_data,
        model_version=MODEL_VERSION,
        generated_at=existing.generated_at,
        updated_at=now,
    ).on_conflict_do_update(
        constraint="uq_day_betting_slip_date_source",
        set_={"slips": full_data, "updated_at": now},
    )
    await db.execute(stmt)
    await db.commit()

    return {
        "slip_date": target_date.isoformat(),
        "slips": full_data,
        "model_version": MODEL_VERSION,
        "generated_at": existing.generated_at.isoformat(),
        "cached": False,
        "source": SOURCE,
    }


# ─── Public entry point ───────────────────────────────────────────────────────

SLIP_NAMES = {
    1: "DC + Trifft",
    2: "Siegerschein",
    3: "Tore Über 1,5",
    4: "DC Kombi",
    6: "Vierer U4,5",
}


async def generate_pattern_slips(
    db: AsyncSession,
    target_date: date | None = None,
    force: bool = False,
) -> dict:
    if target_date is None:
        target_date = date.today()

    if not force:
        existing = (await db.execute(
            select(DayBettingSlip).where(
                DayBettingSlip.slip_date == target_date,
                DayBettingSlip.source == SOURCE,
            )
        )).scalar_one_or_none()
        if existing:
            return {
                "slip_date": target_date.isoformat(),
                "slips": existing.slips,
                "model_version": existing.model_version,
                "generated_at": existing.generated_at.isoformat(),
                "cached": True,
                "source": SOURCE,
            }

    fixtures = await _load_fixtures_with_probs(db, target_date)
    if not fixtures:
        raise ValueError(
            f"Keine Spiele mit MRP-Daten am {target_date}"
        )

    picks1, odd1 = _build_slip1(fixtures)
    picks2, odd2 = _build_slip2(fixtures)
    picks3, odd3 = _build_slip3(fixtures)
    picks4, odd4 = _build_slip4(fixtures)
    picks5, odd5 = _build_slip5(fixtures)
    picks6, odd6 = _build_slip6(fixtures)

    def _slip(nr: int, picks: list[dict], combined: float) -> dict:
        name = SLIP_NAMES[nr]
        n_games = len({p["fixture_id"] for p in picks if not p.get("betbuilder")})
        return {
            "slip_nr": nr,
            "name": name,
            "combined_odd": combined,
            "n_games": n_games,
            "reasoning": f"{name} – {n_games} Spiele · faire Kombinationsquote {combined:.2f}",
            "picks": picks,
        }

    slips = [
        s for s in [
            _slip(1, picks1, odd1),
            _slip(2, picks2, odd2),
            _slip(3, picks3, odd3),
            _slip(4, picks4, odd4),
            _slip(6, picks6, odd6),
        ] if s["picks"]  # skip empty slips (slot 5 deaktiviert)
    ]

    day_summary = (
        f"Pattern-Scheine für {target_date.strftime('%d.%m.%Y')} aus {len(fixtures)} Spielen "
        f"(MRP-Daten, keine KI). Faire Quoten: "
        + " / ".join(f"Schein {s['slip_nr']} {s['combined_odd']:.2f}" for s in slips)
    )

    full_data: dict[str, Any] = {"slips": slips, "day_summary": day_summary}
    now = datetime.utcnow()

    stmt = pg_insert(DayBettingSlip).values(
        slip_date=target_date,
        source=SOURCE,
        slips=full_data,
        model_version=MODEL_VERSION,
        generated_at=now,
        updated_at=now,
    ).on_conflict_do_update(
        constraint="uq_day_betting_slip_date_source",
        set_={"slips": full_data, "model_version": MODEL_VERSION, "updated_at": now},
    )
    await db.execute(stmt)
    await db.commit()

    return {
        "slip_date": target_date.isoformat(),
        "slips": full_data,
        "model_version": MODEL_VERSION,
        "generated_at": now.isoformat(),
        "cached": False,
        "source": SOURCE,
    }
