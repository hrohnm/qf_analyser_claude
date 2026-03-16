"""
Generate 2 betting slips for all fixtures of a given day using Claude.

Each slip must use legs with odds between 1.25 and 1.40 and target
a combined odd of 10-12.
"""
import json
import logging
from datetime import datetime, date

import anthropic
from sqlalchemy import select, cast, Date
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.day_betting_slip import DayBettingSlip
from app.models.fixture import Fixture
from app.models.fixture_injury_impact import FixtureInjuryImpact
from app.models.fixture_odds import FixtureOdds
from app.models.fixture_prediction import FixturePrediction
from app.models.league import League
from app.models.team import Team
from app.models.team_elo_snapshot import TeamEloSnapshot
from app.models.team_form_snapshot import TeamFormSnapshot
from app.services.ai_picks_service import (
    _run_agentic_loop, _parse_odd, BET_ID_LABELS, BETANO_ID
)

logger = logging.getLogger(__name__)
MODEL = "claude-sonnet-4-6"


async def _gather_day_data(db: AsyncSession, target_date: date) -> list[dict]:
    """Collect all fixtures of the day with their odds and key stats."""
    fixtures = (await db.execute(
        select(Fixture)
        .where(cast(Fixture.kickoff_utc, Date) == target_date)
        .order_by(Fixture.kickoff_utc)
    )).scalars().all()

    if not fixtures:
        return []

    fixture_ids = [f.id for f in fixtures]
    team_ids = list({f.home_team_id for f in fixtures} | {f.away_team_id for f in fixtures})
    league_ids = list({f.league_id for f in fixtures})
    season_years = list({f.season_year for f in fixtures})

    # Teams
    teams = {t.id: t for t in (await db.execute(select(Team).where(Team.id.in_(team_ids)))).scalars().all()}
    # Leagues
    leagues = {l.id: l for l in (await db.execute(select(League).where(League.id.in_(league_ids)))).scalars().all()}
    # Elo
    elo_rows = (await db.execute(
        select(TeamEloSnapshot).where(
            TeamEloSnapshot.team_id.in_(team_ids),
            TeamEloSnapshot.season_year.in_(season_years),
        )
    )).scalars().all()
    elo_map = {(e.team_id, e.season_year): e for e in elo_rows}
    # Form
    form_rows = (await db.execute(
        select(TeamFormSnapshot).where(
            TeamFormSnapshot.team_id.in_(team_ids),
            TeamFormSnapshot.season_year.in_(season_years),
            TeamFormSnapshot.window_size == 5,
        )
    )).scalars().all()
    form_map = {(f.team_id, f.league_id, f.scope): f for f in form_rows}
    # Predictions
    preds = {p.fixture_id: p for p in (await db.execute(
        select(FixturePrediction).where(FixturePrediction.fixture_id.in_(fixture_ids))
    )).scalars().all()}
    # Injury impacts – sum per team per fixture
    impact_rows = (await db.execute(
        select(FixtureInjuryImpact).where(FixtureInjuryImpact.fixture_id.in_(fixture_ids))
    )).scalars().all()
    impact_totals: dict[int, dict[int, float]] = {}  # fixture_id -> {team_id -> total}
    for imp in impact_rows:
        impact_totals.setdefault(imp.fixture_id, {})
        impact_totals[imp.fixture_id][imp.team_id] = (
            impact_totals[imp.fixture_id].get(imp.team_id, 0.0) + float(imp.impact_score)
        )
    # All Betano odds
    odds_rows = (await db.execute(
        select(FixtureOdds).where(
            FixtureOdds.fixture_id.in_(fixture_ids),
            FixtureOdds.bookmaker_id == BETANO_ID,
        )
    )).scalars().all()
    odds_by_fixture: dict[int, dict[int, list]] = {}
    for o in odds_rows:
        odds_by_fixture.setdefault(o.fixture_id, {})[o.bet_id] = o.values

    result = []
    for fix in fixtures:
        home = teams.get(fix.home_team_id)
        away = teams.get(fix.away_team_id)
        league = leagues.get(fix.league_id)
        home_elo = elo_map.get((fix.home_team_id, fix.season_year))
        away_elo = elo_map.get((fix.away_team_id, fix.season_year))
        home_form = form_map.get((fix.home_team_id, fix.league_id, "home"))
        away_form = form_map.get((fix.away_team_id, fix.league_id, "away"))
        pred = preds.get(fix.id)
        fix_odds = odds_by_fixture.get(fix.id, {})

        # Bet markets: 1X2, O/U, Doppelchance, + Tore Heimteam (16) / Auswärtsteam (17)
        KEY_BET_IDS = {1: "1X2", 5: "O/U", 12: "Dbl", 16: "HG", 17: "AG"}
        # For HG/AG: sort so Over 0.5 appears first (Betano sometimes puts it at index 6+)
        SORT_FIRST = {"HG": "Over 0.5", "AG": "Over 0.5"}
        formatted_odds: dict[str, object] = {}
        for bet_id, short_label in KEY_BET_IDS.items():
            vals = fix_odds.get(bet_id)
            if vals:
                if short_label in SORT_FIRST:
                    target = SORT_FIRST[short_label]
                    # Put Over 0.5 first if present, then the rest (up to 5 more)
                    priority = [v for v in vals if v.get("value", "") == target]
                    rest = [v for v in vals if v.get("value", "") != target][:5]
                    sorted_vals = priority + rest
                else:
                    sorted_vals = vals[:6]
                formatted_odds[short_label] = [
                    {"v": v.get("value", ""), "o": v.get("odd", "")}
                    for v in sorted_vals
                ]
                formatted_odds[f"_{short_label}_id"] = bet_id  # type: ignore

        # Comparison block from API-Football (spider diagram values, home perspective %)
        def _pf(v) -> float | None:
            return round(float(v), 1) if v is not None else None

        cmp = None
        if pred:
            cmp = {
                "f": [_pf(pred.cmp_form_home),    _pf(pred.cmp_form_away)],     # form
                "a": [_pf(pred.cmp_att_home),      _pf(pred.cmp_att_away)],      # attack
                "d": [_pf(pred.cmp_def_home),      _pf(pred.cmp_def_away)],      # defense
                "p": [_pf(pred.cmp_poisson_home),  _pf(pred.cmp_poisson_away)],  # poisson
                "h": [_pf(pred.cmp_h2h_home),      _pf(pred.cmp_h2h_away)],      # h2h
                "t": [_pf(pred.cmp_total_home),    _pf(pred.cmp_total_away)],    # total
            }

        # Injury impact totals per team
        fix_impacts = impact_totals.get(fix.id, {})
        inj_h = round(fix_impacts.get(fix.home_team_id, 0.0), 1) or None
        inj_a = round(fix_impacts.get(fix.away_team_id, 0.0), 1) or None

        result.append({
            "id": fix.id,
            "home": home.name if home else f"T{fix.home_team_id}",
            "away": away.name if away else f"T{fix.away_team_id}",
            "league": (league.name if league else "?")[:20],
            "ko": fix.kickoff_utc.strftime("%H:%M") if fix.kickoff_utc else None,
            # Elo + Form
            "h_elo": round(float(home_elo.elo_overall)) if home_elo and home_elo.elo_overall else None,
            "a_elo": round(float(away_elo.elo_overall)) if away_elo and away_elo.elo_overall else None,
            "h_form": round(float(home_form.form_score)) if home_form and home_form.form_score else None,
            "a_form": round(float(away_form.form_score)) if away_form and away_form.form_score else None,
            # API-Football Vorhersage (Gewinner, Siegchancen %, Over/Under)
            "pred": {
                "w": pred.winner_name if pred else None,
                "ph": _pf(pred.percent_home) if pred else None,
                "pd": _pf(pred.percent_draw) if pred else None,
                "pa": _pf(pred.percent_away) if pred else None,
                "ou": pred.under_over if pred else None,
                # Last 5 stats (goals avg)
                "h_gfa": _pf(pred.home_last5_goals_for_avg),
                "h_gaa": _pf(pred.home_last5_goals_against_avg),
                "a_gfa": _pf(pred.away_last5_goals_for_avg),
                "a_gaa": _pf(pred.away_last5_goals_against_avg),
                # Season (clean sheets, failed to score)
                "h_cs": pred.home_clean_sheet_total,
                "a_cs": pred.away_clean_sheet_total,
            } if pred else None,
            # Spider-Diagramm (API-Football Vergleich heim% / ausw%)
            # f=Form, a=Angriff, d=Defensive, p=Poisson, h=H2H, t=Gesamt
            "cmp": cmp,
            # Verletzungs-Impact (Summe pro Team, höher = mehr Ausfälle)
            "inj_h": inj_h,
            "inj_a": inj_a,
            # Betano-Quoten: 1X2, Over/Under, Doppelchance, HG=Heimtore, AG=Auswärtststore
            "odds": formatted_odds,
        })

    return result


SLIPS_SYSTEM_PROMPT = """Du bist ein professioneller Sportwetten-Analyst.

DATENFELDER (komprimiert):
- id/home/away/league/ko: Basis
- h_elo/a_elo: Elo-Ratings (höher=stärker), h_form/a_form: Formscores 0-100
- pred: API-Vorhersage {w=Favorit, ph/pd/pa=Siegchance%, ou=Over/Under, h_gfa/a_gfa=Tore-Ø letzte 5, h_gaa/a_gaa=Gegentore-Ø letzte 5, h_cs/a_cs=Clean Sheets Saison}
- cmp: Spider-Diagramm [Heim%, Ausw%] für f=Form, a=Angriff, d=Defensive, p=Poisson, h=H2H, t=Gesamt
- inj_h/inj_a: Verletzungs-Impact-Summe (0=keine Ausfälle, >50=schwere Ausfälle)
- odds: Betano-Quoten {1X2=[Home/Draw/Away], O/U=[Over2.5/Under2.5...], Dbl=[Home/Draw,Home/Away,Draw/Away], HG=[Over0.5,Over1.5...Heimteam-Tore], AG=[Over0.5,Over1.5...Auswärtsteam-Tore]}

ERSTELLE EXAKT 2 WETTSCHEINE.

REGELN FUER BEIDE SCHEINE:
- Jeder Pick muss eine Einzelquote zwischen 1.25 und 1.40 haben.
- Betbuilder sind erlaubt, aber nur wenn die ausgegebene Leg-Quote ebenfalls zwischen 1.25 und 1.40 liegt.
- Die Gesamtquote jedes Scheins muss EXAKT im Bereich 10.00 bis 12.00 liegen.
- Egal welche Picks: Marktwahl ist frei, solange die Quotenregel eingehalten wird.
- Nutze bevorzugt viele solide Picks statt weniger riskanter Picks.
- Vermeide Quoten ausserhalb des Bereichs kompromisslos.

PRAKTISCHE FOLGE:
- Meist werden 7 bis 11 Picks pro Schein noetig sein.
- Rechne die Gesamtquote vor dem Abschicken exakt nach.
- Wenn ein Schein unter 10 liegt, fuege weitere Picks hinzu.
- Wenn ein Schein ueber 12 liegt, ersetze Picks durch niedrigere Quoten.

Antworte NUR mit validem JSON:

{
  "slips": [
    {
      "slip_nr": 1,
      "combined_odd": 10.24,
      "reasoning": "Kurze Begründung (max. 1 Satz)",
      "picks": [
        {
          "fixture_id": 123,
          "home": "A", "away": "B", "league": "Liga", "kickoff": "19:45",
          "market": "Doppelchance",
          "pick": "Home/Draw",
          "bet_id": 12,
          "bet_value": "Home/Draw",
          "odd": 1.28,
          "betbuilder": false,
          "reasoning": "Kurz",
          "result": null
        },
        {
          "fixture_id": 123,
          "home": "A", "away": "B", "league": "Liga", "kickoff": "19:45",
          "market": "Heimteam erzielt",
          "pick": "Over 0.5",
          "bet_id": 16,
          "bet_value": "Over 0.5",
          "odd": 1.30,
          "betbuilder": true,
          "reasoning": "Kurz",
          "result": null
        }
      ]
    },
    {
      "slip_nr": 2,
      "combined_odd": 10.78,
      "reasoning": "Kurze Begründung (max. 1 Satz)",
      "picks": [
        {
          "fixture_id": 456,
          "home": "C", "away": "D", "league": "Liga", "kickoff": "21:00",
          "market": "Unter 4.5 Tore",
          "pick": "Under 4.5",
          "bet_id": 5,
          "bet_value": "Under 4.5",
          "odd": 1.32,
          "betbuilder": false,
          "reasoning": "Kurz",
          "result": null
        }
      ]
    }
  ],
  "day_summary": "1-2 Sätze"
}

Regeln: genau 2 Scheine. bet_value EXAKT aus odds übernehmen. result=null. Kein Text außerhalb JSON."""


BETBUILDER_DISCOUNT = 0.87  # ~13% Abschlag für korrelierte Events (DC + Team trifft)


def _validate_slip_shape(slips: list) -> None:
    if len(slips) != 2:
        raise ValueError(f"Es muessen genau 2 Wettscheine erzeugt werden, erhalten: {len(slips)}")

    for idx, slip in enumerate(slips, start=1):
        picks = slip.get("picks", [])
        if not picks:
            raise ValueError(f"Schein {idx} enthaelt keine Picks")

        combined = slip.get("combined_odd")
        try:
            combined_val = float(combined)
        except (TypeError, ValueError):
            raise ValueError(f"Schein {idx} hat keine gueltige Gesamtquote")
        if not (10.0 <= combined_val <= 12.0):
            raise ValueError(f"Schein {idx} liegt mit Gesamtquote {combined_val:.2f} ausserhalb 10-12")

        for pick_idx, pick in enumerate(picks, start=1):
            odd = pick.get("odd")
            try:
                odd_val = float(odd)
            except (TypeError, ValueError):
                continue
            if not (1.25 <= odd_val <= 1.40):
                raise ValueError(
                    f"Schein {idx}, Pick {pick_idx} hat Quote {odd_val:.2f} ausserhalb 1.25-1.40"
                )


def _validate_slip_odds(slips: list, all_fixture_odds: dict[int, dict[int, list]]) -> list:
    """
    Validate odds from DB and recalculate combined_odd with betbuilder discount.

    Betbuilder pairs (same fixture_id, betbuilder=true on 2nd pick) are priced
    at product × BETBUILDER_DISCOUNT instead of raw product, because bookmakers
    apply a correlation discount for dependent events (e.g. DC + team scores).
    """
    for slip in slips:
        picks = slip.get("picks", [])
        calc_odd = 1.0
        prev_fixture_id = None

        for i, pick in enumerate(picks):
            bet_id = pick.get("bet_id")
            bet_value = pick.get("bet_value")
            fixture_id = pick.get("fixture_id")
            is_betbuilder = pick.get("betbuilder", False)

            # Validate odd against DB
            fix_odds = all_fixture_odds.get(fixture_id, {})
            if bet_id and bet_value:
                values = fix_odds.get(int(bet_id), [])
                matched = next(
                    (v for v in values if str(v.get("value", "")).strip() == str(bet_value).strip()),
                    None,
                )
                if matched:
                    pick["odd"] = _parse_odd(matched.get("odd"))
                else:
                    pick["odd"] = None
                    logger.warning("Slip odds not found: fixture=%s bet_id=%s val=%r",
                                   fixture_id, bet_id, bet_value)

            pick["result"] = pick.get("result")  # keep null

            if pick.get("odd"):
                if is_betbuilder and fixture_id == prev_fixture_id:
                    # Betbuilder: replace last simple multiplication with discounted one
                    # Undo previous pick's multiplication, then apply pair with discount
                    prev_odd = picks[i - 1].get("odd", 1.0) or 1.0
                    calc_odd /= prev_odd          # undo
                    calc_odd *= prev_odd * pick["odd"] * BETBUILDER_DISCOUNT
                else:
                    calc_odd *= pick["odd"]

            prev_fixture_id = fixture_id

        slip["combined_odd"] = round(calc_odd, 2)
    return slips


def _collect_missing_odds(slips: list) -> list[dict]:
    missing: list[dict] = []
    for slip in slips:
        for pick in slip.get("picks", []):
            if pick.get("odd") is None:
                missing.append({
                    "slip_nr": slip.get("slip_nr"),
                    "fixture_id": pick.get("fixture_id"),
                    "market": pick.get("market"),
                    "bet_id": pick.get("bet_id"),
                    "bet_value": pick.get("bet_value"),
                })
    return missing


async def generate_betting_slips(
    db: AsyncSession,
    target_date: date | None = None,
    force: bool = False,
) -> dict:
    if not settings.anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY not configured")

    if target_date is None:
        target_date = date.today()

    # Return cached unless forced or cached data is empty
    if not force:
        existing = (await db.execute(
            select(DayBettingSlip).where(
                DayBettingSlip.slip_date == target_date,
                DayBettingSlip.source == "ai",
            )
        )).scalar_one_or_none()
        if existing:
            cached_slips = existing.slips.get("slips", []) if isinstance(existing.slips, dict) else []
            if cached_slips:  # only serve cache if it actually has slips
                return {
                    "slip_date": target_date.isoformat(),
                    "slips": existing.slips,
                    "model_version": existing.model_version,
                    "generated_at": existing.generated_at.isoformat(),
                    "cached": True,
                }

    fixtures_data = await _gather_day_data(db, target_date)
    if not fixtures_data:
        raise ValueError(f"Keine Spiele am {target_date}")

    # Build odds lookup for validation from compact format
    # Compact format: {"1X2": [{v,o}], "_1X2_id": 1, ...}
    SHORT_TO_BET_ID = {"1X2": 1, "O/U": 5, "Dbl": 12, "HG": 16, "AG": 17}
    all_fixture_odds: dict[int, dict[int, list]] = {}
    for fix in fixtures_data:
        fix_odds: dict[int, list] = {}
        for short, bet_id in SHORT_TO_BET_ID.items():
            vals_compact = fix.get("odds", {}).get(short, [])
            if vals_compact:
                fix_odds[bet_id] = [{"value": v["v"], "odd": v["o"]} for v in vals_compact if "v" in v]
        all_fixture_odds[fix["id"]] = fix_odds

    user_message = (
        f"Erstelle exakt 2 Wettscheine fuer den Spieltag {target_date.strftime('%d.%m.%Y')}.\n"
        f"Jeder Pick muss Quote 1.25-1.40 haben und jeder Schein Gesamtquote 10-12.\n\n"
        f"SCHRITT 1: Recherchiere aktuelle Verletzungen, Sperren und Neuigkeiten für die interessantesten Spiele.\n\n"
        f"SCHRITT 2: Erstelle die 2 Scheine basierend auf Recherche + folgenden Spieltagsdaten:\n\n"
        f"{json.dumps(fixtures_data, ensure_ascii=False, indent=2)}"
    )

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    # No web search – prompt already has comprehensive data (odds + stats)
    # Retry up to 3× with 70s backoff on rate limit
    import time
    last_err = None
    for attempt in range(3):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=6000,
                system=SLIPS_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )
            if response.stop_reason == "max_tokens":
                logger.warning("Claude response truncated by max_tokens – increase further if needed")
            break
        except anthropic.RateLimitError as e:
            last_err = e
            if attempt < 2:
                wait = 70 * (attempt + 1)
                logger.warning("Rate limit hit, retrying in %ds (attempt %d/3)", wait, attempt + 1)
                time.sleep(wait)
            else:
                raise
    raw = next(b.text for b in response.content if hasattr(b, "text")).strip()

    # Strip markdown fences
    if "```" in raw:
        parts = raw.split("```")
        # Take the part after first fence
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip().rstrip("`").strip()

    # Find JSON object bounds in case there's surrounding text
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start >= 0 and end > start:
        raw = raw[start:end]

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error("JSON parse error. raw[:200]=%r error=%s", raw[:200], e)
        raise ValueError(f"Claude returned invalid JSON: {e}")
    _validate_slip_shape(parsed.get("slips", []))
    slips = _validate_slip_odds(parsed.get("slips", []), all_fixture_odds)
    _validate_slip_shape(slips)
    missing_odds = _collect_missing_odds(slips)
    if missing_odds:
        sample = ", ".join(
            f"S{m['slip_nr']} F{m['fixture_id']} {m['market']}={m['bet_value']}"
            for m in missing_odds[:5]
        )
        raise ValueError(
            f"KI-Wettscheine wurden nicht gespeichert: {len(missing_odds)} Picks ohne Betano-Quote. "
            f"Beispiele: {sample}"
        )
    day_summary = parsed.get("day_summary", "")

    # Store full result
    full_data = {"slips": slips, "day_summary": day_summary}
    now = datetime.utcnow()
    stmt = pg_insert(DayBettingSlip).values(
        slip_date=target_date,
        source="ai",
        slips=full_data,
        model_version=MODEL,
        generated_at=now,
        updated_at=now,
    ).on_conflict_do_update(
        constraint="uq_day_betting_slip_date_source",
        set_={"slips": full_data, "model_version": MODEL, "updated_at": now},
    )
    await db.execute(stmt)
    await db.commit()

    logger.info("Betting slips generated for %s (%d slips)", target_date, len(slips))
    return {
        "slip_date": target_date.isoformat(),
        "slips": slips,
        "day_summary": day_summary,
        "model_version": MODEL,
        "generated_at": now.isoformat(),
        "cached": False,
    }
