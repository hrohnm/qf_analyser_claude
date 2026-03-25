from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.day_betting_slip import DayBettingSlip
from app.models.fixture import Fixture
from app.models.placed_bet import PlacedBet
from app.services.betting_slips_service import generate_betting_slips
from app.services.pattern_slips_service import generate_pattern_slips, regenerate_single_slip, generate_custom_slip
from app.services.slip_evaluation_service import evaluate_slips_for_date

router = APIRouter(prefix="/betting-slips", tags=["Betting Slips"])


async def _enrich_slips_with_fixture_state(db: AsyncSession, slips_payload: dict | list | None) -> dict | list | None:
    if slips_payload is None:
        return slips_payload

    root = dict(slips_payload) if isinstance(slips_payload, dict) else {"slips": list(slips_payload)}
    slips = list(root.get("slips", []))

    fixture_ids: set[int] = set()
    for slip in slips:
        for pick in slip.get("picks", []):
            fixture_id = pick.get("fixture_id")
            if isinstance(fixture_id, int):
                fixture_ids.add(fixture_id)

    if not fixture_ids:
        return root if isinstance(slips_payload, dict) else root["slips"]

    fixtures = (
        await db.execute(select(Fixture).where(Fixture.id.in_(fixture_ids)))
    ).scalars().all()
    fixture_map = {fixture.id: fixture for fixture in fixtures}

    enriched_slips: list[dict] = []
    for slip in slips:
        enriched_picks: list[dict] = []
        for pick in slip.get("picks", []):
            updated_pick = dict(pick)
            fixture_id = updated_pick.get("fixture_id")
            fixture = fixture_map.get(fixture_id)
            if fixture is not None:
                updated_pick["fixture_status_short"] = fixture.status_short
                updated_pick["fixture_home_score"] = fixture.home_score
                updated_pick["fixture_away_score"] = fixture.away_score
                updated_pick["fixture_home_ht_score"] = fixture.home_ht_score
                updated_pick["fixture_away_ht_score"] = fixture.away_ht_score
            enriched_picks.append(updated_pick)
        enriched_slip = dict(slip)
        enriched_slip["picks"] = enriched_picks
        enriched_slips.append(enriched_slip)

    root["slips"] = enriched_slips
    return root if isinstance(slips_payload, dict) else root["slips"]


@router.post("/generate")
async def generate(
    slip_date: date | None = None,
    force: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """Generiert 2 Wettscheine fuer den angegebenen Tag via Claude AI."""
    try:
        return await generate_betting_slips(db, slip_date, force=force)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler bei der Generierung: {e}")


@router.get("/")
async def get_slips(
    slip_date: date | None = None,
    source: str = "ai",
    db: AsyncSession = Depends(get_db),
):
    """Lädt gespeicherte Wettscheine für einen Tag (source: 'ai' oder 'pattern')."""
    target = slip_date or date.today()
    row = (await db.execute(
        select(DayBettingSlip).where(
            DayBettingSlip.slip_date == target,
            DayBettingSlip.source == source,
        )
    )).scalar_one_or_none()
    if not row:
        return None
    enriched_slips = await _enrich_slips_with_fixture_state(db, row.slips)
    return {
        "slip_date": row.slip_date.isoformat(),
        "slips": enriched_slips,
        "model_version": row.model_version,
        "generated_at": row.generated_at.isoformat(),
        "cached": True,
        "source": row.source,
    }


@router.post("/generate-pattern")
async def generate_pattern(
    slip_date: date | None = None,
    force: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """Generiert 2 Pattern-basierte Wettscheine (keine KI) fuer den angegebenen Tag."""
    try:
        return await generate_pattern_slips(db, slip_date, force=force)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler: {e}")


class CustomSlipBody(BaseModel):
    slip_date: date | None = None
    league_ids: list[int] | None = None
    fixture_ids: list[int] | None = None
    target_odd: float = 10.0
    min_picks: int = 3
    max_picks: int = 10
    pick_odd_lo: float = 1.20
    pick_odd_hi: float = 1.80
    name: str | None = None


@router.post("/generate-custom")
async def generate_custom(body: CustomSlipBody, db: AsyncSession = Depends(get_db)):
    """Generiert einen Wettschein aus gewählten Ligen/Spielen und einer Zielquote."""
    target = body.slip_date or date.today()
    try:
        slip = await generate_custom_slip(
            db,
            target_date=target,
            league_ids=body.league_ids,
            fixture_ids=body.fixture_ids,
            target_odd=body.target_odd,
            min_picks=body.min_picks,
            max_picks=body.max_picks,
            pick_odd_lo=body.pick_odd_lo,
            pick_odd_hi=body.pick_odd_hi,
            name=body.name,
        )
        return {"slip_date": target.isoformat(), "slip": slip}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler bei der Generierung: {e}")


@router.post("/regenerate-slip")
async def regenerate_slip(
    slip_date: date,
    slip_nr: int,
    db: AsyncSession = Depends(get_db),
):
    """Regeneriert einen einzelnen Pattern-Schein (z.B. wenn ein Spiel nicht verfügbar ist)."""
    try:
        return await regenerate_single_slip(db, slip_date, slip_nr)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler: {e}")


@router.patch("/results")
async def update_slip_results(
    slip_date: date | None = None,
    updates: list[dict] = None,   # [{slip_nr:1, pick_index:0, result:"win"}]
    db: AsyncSession = Depends(get_db),
):
    """Trägt Ergebnisse (win/loss/push) für einzelne Picks nach dem Spieltag ein."""
    target = slip_date or date.today()
    row = (await db.execute(
        select(DayBettingSlip).where(DayBettingSlip.slip_date == target)
    )).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Keine Scheine für dieses Datum")

    full_data = dict(row.slips)
    slips = list(full_data.get("slips", []))

    for u in (updates or []):
        slip_nr = u.get("slip_nr")
        pick_idx = u.get("pick_index")
        result_val = u.get("result")
        if result_val not in ("win", "loss", "push", None):
            raise HTTPException(status_code=400, detail=f"Ungültiges result: {result_val}")
        slip = next((s for s in slips if s.get("slip_nr") == slip_nr), None)
        if slip and pick_idx is not None:
            picks = list(slip.get("picks", []))
            if 0 <= pick_idx < len(picks):
                picks[pick_idx] = {**picks[pick_idx], "result": result_val}
            slip["picks"] = picks

    full_data["slips"] = slips
    await db.execute(
        update(DayBettingSlip)
        .where(DayBettingSlip.slip_date == target)
        .values(slips=full_data)
    )
    await db.commit()
    return {"slip_date": target.isoformat(), "slips": slips}


@router.post("/place-all")
async def place_all(
    slip_date: date | None = None,
    source: str | None = None,
    stake: float = 10.0,
    db: AsyncSession = Depends(get_db),
):
    """Markiert alle Scheine eines Tages als angespielt (falls noch nicht geschehen)."""
    target = slip_date or date.today()
    q = select(DayBettingSlip).where(DayBettingSlip.slip_date == target)
    if source:
        q = q.where(DayBettingSlip.source == source)
    slip_rows = (await db.execute(q)).scalars().all()

    placed_q = select(PlacedBet).where(PlacedBet.slip_date == target)
    if source:
        placed_q = placed_q.where(PlacedBet.source == source)
    existing = {
        (b.source, b.slip_nr) for b in (await db.execute(placed_q)).scalars().all()
    }

    created = 0
    for row in slip_rows:
        raw_slips = row.slips.get("slips", []) if isinstance(row.slips, dict) else []
        for slip in raw_slips:
            key = (row.source, slip["slip_nr"])
            if key in existing:
                continue
            db.add(PlacedBet(
                slip_date=target,
                source=row.source,
                slip_nr=slip["slip_nr"],
                slip_name=slip.get("name") or f"Schein {slip['slip_nr']}",
                combined_odd=slip.get("combined_odd", 0),
                stake=stake,
                status="placed",
            ))
            created += 1

    await db.commit()
    return {"slip_date": target.isoformat(), "created": created, "stake": stake}


@router.post("/evaluate")
async def evaluate(
    slip_date: date | None = None,
    source: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Wertet alle angespielten Scheine eines Tages gegen echte Spielergebnisse aus."""
    target = slip_date or date.today()
    try:
        result = await evaluate_slips_for_date(db, target, source)
        return {"slip_date": target.isoformat(), **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_history(
    days: int = Query(default=14, le=60),
    source: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Gibt alle gespeicherten Scheine der letzten N Tage mit Angespielt-Status zurück."""
    q = select(DayBettingSlip).order_by(DayBettingSlip.slip_date.desc())
    if source:
        q = q.where(DayBettingSlip.source == source)
    q = q.limit(days * 2)  # *2 weil ai + pattern pro Tag
    slip_rows = (await db.execute(q)).scalars().all()

    if not slip_rows:
        return []

    dates = list({r.slip_date for r in slip_rows})
    placed_q = select(PlacedBet).where(PlacedBet.slip_date.in_(dates))
    if source:
        placed_q = placed_q.where(PlacedBet.source == source)
    placed_rows = (await db.execute(placed_q)).scalars().all()
    placed_map: dict[tuple, PlacedBet] = {
        (b.slip_date, b.source, b.slip_nr): b for b in placed_rows
    }

    # Group by date
    days_map: dict[date, list] = {}
    for row in slip_rows:
        raw_slips = row.slips.get("slips", []) if isinstance(row.slips, dict) else []
        for slip in raw_slips:
            slip_nr = slip.get("slip_nr")
            pb = placed_map.get((row.slip_date, row.source, slip_nr))
            entry = {
                "source": row.source,
                "slip_nr": slip_nr,
                "name": slip.get("name") or f"Schein {slip_nr}",
                "combined_odd": slip.get("combined_odd"),
                "n_games": slip.get("n_games"),
                "placed": {
                    "id": pb.id,
                    "status": pb.status,
                    "stake": float(pb.stake) if pb.stake is not None else None,
                    "combined_odd": float(pb.combined_odd),
                    "settled_at": pb.settled_at.isoformat() if pb.settled_at else None,
                } if pb else None,
            }
            days_map.setdefault(row.slip_date, []).append(entry)

    return [
        {"slip_date": d.isoformat(), "slips": slips}
        for d, slips in sorted(days_map.items(), reverse=True)
    ]


# ─── Placed Bets ──────────────────────────────────────────────────────────────

def _bet_to_dict(b: PlacedBet) -> dict:
    return {
        "id": b.id,
        "slip_date": b.slip_date.isoformat(),
        "source": b.source,
        "slip_nr": b.slip_nr,
        "slip_name": b.slip_name,
        "combined_odd": float(b.combined_odd),
        "stake": float(b.stake) if b.stake is not None else None,
        "status": b.status,
        "placed_at": b.placed_at.isoformat(),
        "settled_at": b.settled_at.isoformat() if b.settled_at else None,
    }


class PlaceStrategyBody(BaseModel):
    slip_date: date
    source: str                  # 'pattern' | 'ai'
    stakes: dict[str, float]     # slip_name → stake (0 = überspringen)


@router.post("/place-strategy")
async def place_strategy(body: PlaceStrategyBody, db: AsyncSession = Depends(get_db)):
    """Markiert alle Scheine eines Tages mit Strategie-Einsätzen als angespielt."""
    rows = (await db.execute(
        select(DayBettingSlip).where(
            DayBettingSlip.slip_date == body.slip_date,
            DayBettingSlip.source == body.source,
        )
    )).scalars().all()

    existing = {
        (b.source, b.slip_nr)
        for b in (await db.execute(
            select(PlacedBet).where(
                PlacedBet.slip_date == body.slip_date,
                PlacedBet.source == body.source,
            )
        )).scalars().all()
    }

    created = skipped = 0
    for row in rows:
        for slip in (row.slips.get("slips", []) if isinstance(row.slips, dict) else []):
            name = slip.get("name") or f"Schein {slip['slip_nr']}"
            stake = body.stakes.get(name, 0)
            if stake <= 0:
                skipped += 1
                continue
            if (row.source, slip["slip_nr"]) in existing:
                skipped += 1
                continue
            db.add(PlacedBet(
                slip_date=body.slip_date,
                source=row.source,
                slip_nr=slip["slip_nr"],
                slip_name=name,
                combined_odd=slip.get("combined_odd", 0),
                stake=stake,
                status="placed",
            ))
            created += 1

    await db.commit()
    return {"created": created, "skipped": skipped}


@router.get("/stats-by-slip")
async def get_stats_by_slip(
    source: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Aggregierte Statistiken gruppiert nach Scheinname."""
    q = select(PlacedBet).where(PlacedBet.status.in_(["won", "lost"]))
    if source:
        q = q.where(PlacedBet.source == source)
    bets = (await db.execute(q)).scalars().all()

    by_name: dict[str, dict] = {}
    for b in bets:
        name = b.slip_name or f"Schein {b.slip_nr}"
        if name not in by_name:
            by_name[name] = {"won": 0, "lost": 0, "profit": 0.0, "odds": []}
        by_name[name][b.status] += 1
        by_name[name]["odds"].append(float(b.combined_odd))
        stake = float(b.stake) if b.stake else 0
        if b.status == "won":
            by_name[name]["profit"] += stake * float(b.combined_odd) - stake
        else:
            by_name[name]["profit"] -= stake

    result = []
    for name, d in by_name.items():
        total = d["won"] + d["lost"]
        wr = d["won"] / total if total else 0
        avg_odd = sum(d["odds"]) / len(d["odds"]) if d["odds"] else 0
        ev = wr * avg_odd - 1
        result.append({
            "name": name,
            "won": d["won"],
            "lost": d["lost"],
            "total": total,
            "win_rate": round(wr, 3),
            "avg_odd": round(avg_odd, 3),
            "ev": round(ev, 3),
            "profit": round(d["profit"], 2),
        })

    return sorted(result, key=lambda x: -x["win_rate"])


class PlaceBetBody(BaseModel):
    slip_date: date
    source: str            # 'ai' | 'pattern'
    slip_nr: int
    slip_name: str | None = None
    combined_odd: float
    stake: float | None = None


class SettleBetBody(BaseModel):
    status: str            # 'won' | 'lost' | 'void'


@router.post("/placed")
async def place_bet(body: PlaceBetBody, db: AsyncSession = Depends(get_db)):
    """Markiert einen Schein als 'angespielt'."""
    existing = (await db.execute(
        select(PlacedBet).where(
            PlacedBet.slip_date == body.slip_date,
            PlacedBet.source == body.source,
            PlacedBet.slip_nr == body.slip_nr,
        )
    )).scalar_one_or_none()
    if existing:
        # Update stake if provided
        if body.stake is not None:
            existing.stake = body.stake
        await db.commit()
        return _bet_to_dict(existing)

    bet = PlacedBet(
        slip_date=body.slip_date,
        source=body.source,
        slip_nr=body.slip_nr,
        slip_name=body.slip_name,
        combined_odd=body.combined_odd,
        stake=body.stake,
        status="placed",
    )
    db.add(bet)
    await db.commit()
    await db.refresh(bet)
    return _bet_to_dict(bet)


@router.patch("/placed/{bet_id}")
async def settle_bet(bet_id: int, body: SettleBetBody, db: AsyncSession = Depends(get_db)):
    """Trägt das Ergebnis ein: 'won', 'lost' oder 'void'."""
    if body.status not in ("won", "lost", "void"):
        raise HTTPException(status_code=400, detail="Ungültiger Status")
    bet = (await db.execute(select(PlacedBet).where(PlacedBet.id == bet_id))).scalar_one_or_none()
    if not bet:
        raise HTTPException(status_code=404, detail="Schein nicht gefunden")
    bet.status = body.status
    bet.settled_at = datetime.utcnow()
    await db.commit()
    return _bet_to_dict(bet)


@router.delete("/placed/{bet_id}")
async def unplace_bet(bet_id: int, db: AsyncSession = Depends(get_db)):
    """Entfernt die 'Angespielt'-Markierung."""
    bet = (await db.execute(select(PlacedBet).where(PlacedBet.id == bet_id))).scalar_one_or_none()
    if not bet:
        raise HTTPException(status_code=404, detail="Schein nicht gefunden")
    await db.delete(bet)
    await db.commit()
    return {"deleted": True}


@router.get("/placed")
async def get_placed_bets(
    slip_date: date | None = None,
    source: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Gibt alle angespielten Scheine für ein Datum zurück."""
    q = select(PlacedBet)
    if slip_date:
        q = q.where(PlacedBet.slip_date == slip_date)
    if source:
        q = q.where(PlacedBet.source == source)
    rows = (await db.execute(q.order_by(PlacedBet.slip_date.desc(), PlacedBet.placed_at.desc()))).scalars().all()
    return [_bet_to_dict(b) for b in rows]


@router.get("/stats")
async def get_stats(
    from_date: date | None = None,
    to_date: date | None = None,
    source: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Aggregierte Statistiken über angespielte Scheine."""
    q = select(PlacedBet).where(PlacedBet.status != "placed")  # only settled
    if from_date:
        q = q.where(PlacedBet.slip_date >= from_date)
    if to_date:
        q = q.where(PlacedBet.slip_date <= to_date)
    if source:
        q = q.where(PlacedBet.source == source)

    all_settled = (await db.execute(q)).scalars().all()

    # Also count pending (placed but not settled)
    q_placed = select(func.count()).select_from(PlacedBet).where(PlacedBet.status == "placed")
    if from_date:
        q_placed = q_placed.where(PlacedBet.slip_date >= from_date)
    if to_date:
        q_placed = q_placed.where(PlacedBet.slip_date <= to_date)
    if source:
        q_placed = q_placed.where(PlacedBet.source == source)
    pending = (await db.execute(q_placed)).scalar() or 0

    won = [b for b in all_settled if b.status == "won"]
    lost = [b for b in all_settled if b.status == "lost"]
    settled = len(all_settled)

    total_staked = sum(float(b.stake) for b in all_settled if b.stake is not None)
    total_return = sum(float(b.stake) * float(b.combined_odd) for b in won if b.stake is not None)
    net_profit = total_return - sum(float(b.stake) for b in all_settled if b.stake is not None and b.status in ("won", "lost"))

    return {
        "total_placed": settled + pending,
        "settled": settled,
        "pending": pending,
        "won": len(won),
        "lost": len(lost),
        "win_rate": round(len(won) / settled, 3) if settled > 0 else None,
        "total_staked": round(total_staked, 2) if total_staked else None,
        "total_return": round(total_return, 2) if total_return else None,
        "net_profit": round(net_profit, 2) if total_staked else None,
        "avg_odd_won": round(sum(float(b.combined_odd) for b in won) / len(won), 2) if won else None,
        "avg_odd_lost": round(sum(float(b.combined_odd) for b in lost) / len(lost), 2) if lost else None,
    }
