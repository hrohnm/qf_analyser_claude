"""
Evaluates placed betting slips against actual match results.

For each PlacedBet with status='placed', finds the corresponding DayBettingSlip,
checks every pick against Fixture results, and marks the bet as 'won' or 'lost'.

Evaluation rules (keyed by bet_id + bet_value):
  bet_id=1   Match Winner:     Home/Away/Draw
  bet_id=12  Double Chance:    Home/Draw (1X), Draw/Away (X2), Home/Away (12)
  bet_id=5   Goals Over/Under: Over X.5 / Under X.5
  bet_id=8   BTTS:             Yes / No
  bet_id=16  Home scores:      Over 0.5
  bet_id=17  Away scores:      Over 0.5
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.day_betting_slip import DayBettingSlip
from app.models.fixture import Fixture
from app.models.placed_bet import PlacedBet

logger = logging.getLogger(__name__)

FINISHED_STATUSES = {"FT", "AET", "PEN", "AWD", "WO"}


def _evaluate_pick(pick: dict, fixture: Fixture) -> bool | None:
    """
    Returns True (won), False (lost), or None (undecidable / match not finished).
    """
    if fixture.status_short not in FINISHED_STATUSES:
        return None
    if fixture.home_score is None or fixture.away_score is None:
        return None

    h = fixture.home_score
    a = fixture.away_score
    total = h + a
    bet_id: int | None = pick.get("bet_id")
    bet_value: str = str(pick.get("bet_value") or pick.get("pick") or "")
    bv = bet_value.strip().lower()

    # ── Match Winner (1X2) ──────────────────────────────────────────────────
    if bet_id == 1:
        if bv in ("home", "heimsieg"):
            return h > a
        if bv in ("away", "auswärtssieg"):
            return a > h
        if bv in ("draw", "unentschieden"):
            return h == a

    # ── Double Chance ────────────────────────────────────────────────────────
    elif bet_id == 12:
        if bv in ("home/draw", "1x"):
            return h >= a
        if bv in ("draw/away", "x2"):
            return a >= h
        if bv in ("home/away", "12"):
            return h != a

    # ── Goals Over/Under ────────────────────────────────────────────────────
    elif bet_id == 5:
        m = re.match(r"(over|under)\s*(\d+(?:\.\d+)?)", bv, re.IGNORECASE)
        if m:
            direction = m.group(1).lower()
            threshold = float(m.group(2))
            return (total > threshold) if direction == "over" else (total < threshold)

    # ── Both Teams to Score ─────────────────────────────────────────────────
    elif bet_id == 8:
        if bv in ("yes", "ja"):
            return h > 0 and a > 0
        if bv in ("no", "nein"):
            return h == 0 or a == 0

    # ── Home team to score ───────────────────────────────────────────────────
    elif bet_id == 16:
        m = re.match(r"over\s*(\d+(?:\.\d+)?)", bv, re.IGNORECASE)
        if m:
            return h > float(m.group(1))

    # ── Away team to score ───────────────────────────────────────────────────
    elif bet_id == 17:
        m = re.match(r"over\s*(\d+(?:\.\d+)?)", bv, re.IGNORECASE)
        if m:
            return a > float(m.group(1))

    # Fallback: try to parse market name from pick text
    market = str(pick.get("market") or "").lower()
    pick_text = str(pick.get("pick") or "").lower()

    if "heimsieg" in pick_text or pick_text == "home":
        return h > a
    if "auswärtssieg" in pick_text or pick_text == "away":
        return a > h
    if "unentschieden" in pick_text or pick_text == "draw":
        return h == a
    if "über" in market or "over" in bv:
        m2 = re.search(r"(\d+(?:[.,]\d+)?)", bv or market)
        if m2:
            return total > float(m2.group(1).replace(",", "."))
    if "unter" in market or "under" in bv:
        m2 = re.search(r"(\d+(?:[.,]\d+)?)", bv or market)
        if m2:
            return total < float(m2.group(1).replace(",", "."))

    logger.warning("Cannot evaluate pick: bet_id=%s bet_value=%s market=%s pick=%s",
                   bet_id, bet_value, pick.get("market"), pick.get("pick"))
    return None


async def evaluate_slips_for_date(
    db: AsyncSession,
    target_date: date,
    source: str | None = None,
) -> dict:
    """
    Evaluates all PlacedBets with status='placed' for target_date.
    Returns a summary of what was evaluated.
    """
    q = select(PlacedBet).where(
        PlacedBet.slip_date == target_date,
        PlacedBet.status == "placed",
    )
    if source:
        q = q.where(PlacedBet.source == source)
    placed = (await db.execute(q)).scalars().all()

    if not placed:
        return {"evaluated": 0, "won": 0, "lost": 0, "skipped": 0}

    # Load all DayBettingSlips for the date
    slip_q = select(DayBettingSlip).where(DayBettingSlip.slip_date == target_date)
    if source:
        slip_q = slip_q.where(DayBettingSlip.source == source)
    slip_rows = (await db.execute(slip_q)).scalars().all()
    slip_map: dict[tuple[str, int], list] = {}
    for row in slip_rows:
        raw = row.slips.get("slips", []) if isinstance(row.slips, dict) else []
        for slip in raw:
            slip_map[(row.source, slip["slip_nr"])] = slip.get("picks", [])

    # Collect all fixture IDs needed
    all_fixture_ids: set[int] = set()
    for (src, slip_nr), picks in slip_map.items():
        all_fixture_ids.update(p["fixture_id"] for p in picks if p.get("fixture_id"))

    fixtures = {
        f.id: f for f in (await db.execute(
            select(Fixture).where(Fixture.id.in_(all_fixture_ids))
        )).scalars().all()
    }

    won_count = lost_count = skipped = 0

    for pb in placed:
        picks = slip_map.get((pb.source, pb.slip_nr))
        if not picks:
            logger.warning("No picks found for PlacedBet %s (%s slip %s)", pb.id, pb.source, pb.slip_nr)
            skipped += 1
            continue

        results: list[bool | None] = []
        for pick in picks:
            fid = pick.get("fixture_id")
            if not fid:
                continue
            fixture = fixtures.get(fid)
            if not fixture:
                results.append(None)
                continue
            results.append(_evaluate_pick(pick, fixture))

        # A slip is won only if every decidable pick is won and there's at least one
        decidable = [r for r in results if r is not None]
        if not decidable:
            logger.info("PlacedBet %s: no decidable picks yet, skipping", pb.id)
            skipped += 1
            continue

        all_won = all(decidable)
        pb.status = "won" if all_won else "lost"
        pb.settled_at = datetime.utcnow()
        if all_won:
            won_count += 1
        else:
            lost_count += 1

    await db.commit()
    return {
        "evaluated": won_count + lost_count,
        "won": won_count,
        "lost": lost_count,
        "skipped": skipped,
    }
