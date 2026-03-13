"""
Generate 5 betting picks + top scorer suggestion for a fixture using Claude.

Each pick is enriched with the matching Betano quote (odd) directly from the DB
so results can be tracked and analysed later.

Pick schema stored in DB:
{
  "market": "...",
  "pick": "...",
  "bet_id": 1,          # Betano bet_id (null if no match)
  "bet_value": "Home",  # Exact value string from odds API (null if no match)
  "odd": 1.85,          # Float, null if no Betano line available
  "confidence": "hoch | mittel | niedrig",
  "reasoning": "...",
  "result": null        # "win" | "loss" | "push" – filled later after match
}
"""
import json
import logging
from datetime import datetime

import anthropic
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.fixture import Fixture
from app.models.fixture_ai_pick import FixtureAiPick
from app.models.fixture_goal_probability import FixtureGoalProbability
from app.models.fixture_injury import FixtureInjury
from app.models.fixture_injury_impact import FixtureInjuryImpact
from app.models.fixture_odds import FixtureOdds
from app.models.fixture_prediction import FixturePrediction
from app.models.league import League
from app.models.team import Team
from app.models.team_elo_snapshot import TeamEloSnapshot
from app.models.team_form_snapshot import TeamFormSnapshot

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-6"
BETANO_ID = 32

# Bet IDs we store from Betano – sent to Claude so it can reference exact lines
BET_ID_LABELS = {
    1:   "Match Winner (1X2)         – values: Home / Draw / Away",
    5:   "Goals Over/Under (total)   – values: 'Over X.X' / 'Under X.X'",
    6:   "Goals O/U First Half       – values: 'Over X.X' / 'Under X.X'",
    12:  "Double Chance              – values: 1X / X2 / 12",
    16:  "Total Home Goals           – values: 'Over X.X' / 'Under X.X'",
    17:  "Total Away Goals           – values: 'Over X.X' / 'Under X.X'",
    26:  "Goals O/U Second Half      – values: 'Over X.X' / 'Under X.X'",
    105: "Home Team Goals – 1st Half – values: 'Over X.X' / 'Under X.X'",
    106: "Away Team Goals – 1st Half – values: 'Over X.X' / 'Under X.X'",
}


def _pf(v) -> float | None:
    return float(v) if v is not None else None


def _parse_odd(odd_str: str | None) -> float | None:
    if odd_str is None:
        return None
    try:
        return float(odd_str)
    except (ValueError, TypeError):
        return None


async def _gather_fixture_data(db: AsyncSession, fixture_id: int) -> dict:
    """Collect all relevant data for a fixture into a single dict."""
    fix_row = (await db.execute(select(Fixture).where(Fixture.id == fixture_id))).scalar_one_or_none()
    if not fix_row:
        return {}

    home_team = (await db.execute(select(Team).where(Team.id == fix_row.home_team_id))).scalar_one_or_none()
    away_team = (await db.execute(select(Team).where(Team.id == fix_row.away_team_id))).scalar_one_or_none()
    league = (await db.execute(select(League).where(League.id == fix_row.league_id))).scalar_one_or_none()

    home_name = home_team.name if home_team else f"Team {fix_row.home_team_id}"
    away_name = away_team.name if away_team else f"Team {fix_row.away_team_id}"

    # Elo
    elo_rows = (await db.execute(
        select(TeamEloSnapshot).where(
            TeamEloSnapshot.league_id == fix_row.league_id,
            TeamEloSnapshot.season_year == fix_row.season_year,
            TeamEloSnapshot.team_id.in_([fix_row.home_team_id, fix_row.away_team_id]),
        )
    )).scalars().all()
    elo_map = {e.team_id: e for e in elo_rows}
    home_elo = elo_map.get(fix_row.home_team_id)
    away_elo = elo_map.get(fix_row.away_team_id)

    # Form (scope home/away)
    form_rows = (await db.execute(
        select(TeamFormSnapshot).where(
            TeamFormSnapshot.league_id == fix_row.league_id,
            TeamFormSnapshot.season_year == fix_row.season_year,
            TeamFormSnapshot.window_size == 5,
            TeamFormSnapshot.team_id.in_([fix_row.home_team_id, fix_row.away_team_id]),
            TeamFormSnapshot.scope.in_(["home", "away"]),
        )
    )).scalars().all()
    form_map = {(f.team_id, f.scope): f for f in form_rows}
    home_form = form_map.get((fix_row.home_team_id, "home"))
    away_form = form_map.get((fix_row.away_team_id, "away"))

    # Goal probability
    gp_rows = (await db.execute(
        select(FixtureGoalProbability).where(FixtureGoalProbability.fixture_id == fixture_id)
    )).scalars().all()
    gp_home = next((r for r in gp_rows if r.team_id == fix_row.home_team_id), None)
    gp_away = next((r for r in gp_rows if r.team_id == fix_row.away_team_id), None)

    # Injuries + impacts
    injuries = (await db.execute(
        select(FixtureInjury).where(FixtureInjury.fixture_id == fixture_id)
    )).scalars().all()
    impacts = (await db.execute(
        select(FixtureInjuryImpact).where(FixtureInjuryImpact.fixture_id == fixture_id)
    )).scalars().all()
    impact_by_player = {i.player_id: i for i in impacts if i.player_id}
    home_impact_total = round(sum(float(i.impact_score) for i in impacts if i.team_id == fix_row.home_team_id), 1)
    away_impact_total = round(sum(float(i.impact_score) for i in impacts if i.team_id == fix_row.away_team_id), 1)

    # API-Football prediction
    pred = (await db.execute(
        select(FixturePrediction).where(FixturePrediction.fixture_id == fixture_id)
    )).scalar_one_or_none()

    # All Betano odds – structured per bet_id for Claude to reference
    odds_rows = (await db.execute(
        select(FixtureOdds).where(
            FixtureOdds.fixture_id == fixture_id,
            FixtureOdds.bookmaker_id == BETANO_ID,
        )
    )).scalars().all()
    odds_by_bet_id: dict[int, list] = {o.bet_id: o.values for o in odds_rows}

    # Format odds for Claude: {bet_id: {label, values: [{value, odd}]}}
    available_odds = {}
    for bet_id, label in BET_ID_LABELS.items():
        values = odds_by_bet_id.get(bet_id)
        if values:
            available_odds[str(bet_id)] = {
                "label": label,
                "values": values,
            }

    return {
        "fixture": {
            "id": fix_row.id,
            "kickoff_utc": fix_row.kickoff_utc.isoformat() if fix_row.kickoff_utc else None,
            "matchday": fix_row.matchday,
            "status": fix_row.status_short,
        },
        "league": {"name": league.name if league else None, "country": league.country if league else None},
        "home": {
            "name": home_name,
            "elo": {
                "overall": _pf(home_elo.elo_overall) if home_elo else None,
                "home": _pf(home_elo.elo_home) if home_elo else None,
                "tier": home_elo.strength_tier if home_elo else None,
                "delta_last5": _pf(home_elo.elo_delta_last_5) if home_elo else None,
            },
            "form": {
                "score": _pf(home_form.form_score) if home_form else None,
                "trend": home_form.form_trend if home_form else None,
                "bucket": home_form.form_bucket if home_form else None,
            },
            "goal_prob": {
                "p_ge_1": _pf(gp_home.p_ge_1_goal) if gp_home else None,
                "p_ge_2": _pf(gp_home.p_ge_2_goals) if gp_home else None,
                "p_ge_3": _pf(gp_home.p_ge_3_goals) if gp_home else None,
                "lambda": _pf(gp_home.lambda_weighted) if gp_home else None,
            },
            "injury_impact_total": home_impact_total,
            "injuries": [
                {
                    "player": i.player_name,
                    "type": i.injury_type,
                    "impact": _pf(impact_by_player[i.player_id].impact_score) if i.player_id and i.player_id in impact_by_player else None,
                    "bucket": impact_by_player[i.player_id].impact_bucket if i.player_id and i.player_id in impact_by_player else None,
                }
                for i in injuries if i.team_id == fix_row.home_team_id
            ],
        },
        "away": {
            "name": away_name,
            "elo": {
                "overall": _pf(away_elo.elo_overall) if away_elo else None,
                "away": _pf(away_elo.elo_away) if away_elo else None,
                "tier": away_elo.strength_tier if away_elo else None,
                "delta_last5": _pf(away_elo.elo_delta_last_5) if away_elo else None,
            },
            "form": {
                "score": _pf(away_form.form_score) if away_form else None,
                "trend": away_form.form_trend if away_form else None,
                "bucket": away_form.form_bucket if away_form else None,
            },
            "goal_prob": {
                "p_ge_1": _pf(gp_away.p_ge_1_goal) if gp_away else None,
                "p_ge_2": _pf(gp_away.p_ge_2_goals) if gp_away else None,
                "p_ge_3": _pf(gp_away.p_ge_3_goals) if gp_away else None,
                "lambda": _pf(gp_away.lambda_weighted) if gp_away else None,
            },
            "injury_impact_total": away_impact_total,
            "injuries": [
                {
                    "player": i.player_name,
                    "type": i.injury_type,
                    "impact": _pf(impact_by_player[i.player_id].impact_score) if i.player_id and i.player_id in impact_by_player else None,
                    "bucket": impact_by_player[i.player_id].impact_bucket if i.player_id and i.player_id in impact_by_player else None,
                }
                for i in injuries if i.team_id == fix_row.away_team_id
            ],
        },
        "api_prediction": {
            "winner": pred.winner_name if pred else None,
            "advice": pred.advice if pred else None,
            "percent": {
                "home": _pf(pred.percent_home) if pred else None,
                "draw": _pf(pred.percent_draw) if pred else None,
                "away": _pf(pred.percent_away) if pred else None,
            },
            "under_over": pred.under_over if pred else None,
            "comparison": {
                "form":    {"home": _pf(pred.cmp_form_home),    "away": _pf(pred.cmp_form_away)}    if pred else None,
                "att":     {"home": _pf(pred.cmp_att_home),     "away": _pf(pred.cmp_att_away)}     if pred else None,
                "def":     {"home": _pf(pred.cmp_def_home),     "away": _pf(pred.cmp_def_away)}     if pred else None,
                "poisson": {"home": _pf(pred.cmp_poisson_home), "away": _pf(pred.cmp_poisson_away)} if pred else None,
                "h2h":     {"home": _pf(pred.cmp_h2h_home),     "away": _pf(pred.cmp_h2h_away)}     if pred else None,
                "total":   {"home": _pf(pred.cmp_total_home),   "away": _pf(pred.cmp_total_away)}   if pred else None,
            } if pred else None,
            "home_last5": {
                "form": _pf(pred.home_last5_form), "att": _pf(pred.home_last5_att),
                "def": _pf(pred.home_last5_def),
                "goals_for_avg": _pf(pred.home_last5_goals_for_avg),
                "goals_against_avg": _pf(pred.home_last5_goals_against_avg),
            } if pred else None,
            "away_last5": {
                "form": _pf(pred.away_last5_form), "att": _pf(pred.away_last5_att),
                "def": _pf(pred.away_last5_def),
                "goals_for_avg": _pf(pred.away_last5_goals_for_avg),
                "goals_against_avg": _pf(pred.away_last5_goals_against_avg),
            } if pred else None,
            "home_season": {
                "wins_home": pred.home_wins_home, "wins_away": pred.home_wins_away,
                "draws": pred.home_draws_total, "loses": pred.home_loses_total,
                "clean_sheets": pred.home_clean_sheet_total,
                "goals_for_avg": _pf(pred.home_goals_for_avg_total),
                "goals_against_avg": _pf(pred.home_goals_against_avg_total),
            } if pred else None,
            "away_season": {
                "wins_home": pred.away_wins_home, "wins_away": pred.away_wins_away,
                "draws": pred.away_draws_total, "loses": pred.away_loses_total,
                "clean_sheets": pred.away_clean_sheet_total,
                "goals_for_avg": _pf(pred.away_goals_for_avg_total),
                "goals_against_avg": _pf(pred.away_goals_against_avg_total),
            } if pred else None,
        },
        # All available Betano lines – Claude MUST reference these for bet_id/bet_value/odd
        "betano_odds": available_odds,
    }


SYSTEM_PROMPT = """Du bist ein erfahrener Sportwetten-Analyst mit Expertise in statistischen Fußballmodellen.

Du hast Zugriff auf ein Web-Search-Tool. Nutze es AKTIV um folgende Informationen zu recherchieren BEVOR du die Picks erstellst:
1. Aktuelle Verletzungs- und Sperrnachrichten für BEIDE Teams (die letzten 48-72 Stunden)
2. Ergebnisse der letzten 1-2 Spiele beider Teams (Formcheck)
3. Besondere Umstände: Trainerwechsel, interner Streit, Heimvorteil-Faktoren, Wetter
4. Falls vorhanden: direkten Vergleich (H2H) und historische Tendenzen

Suche auf Deutsch UND Englisch. Nach der Recherche erstellst du die Picks.

WICHTIG für die Picks: Für jeden Pick MUSST du die passende Betano-Quote aus dem Feld "betano_odds" referenzieren:
- "bet_id": die ID des Wettmarkts (z. B. 1 für 1X2, 5 für Over/Under)
- "bet_value": der EXAKTE "value"-String aus den Quoten (z. B. "Home", "Over 2.5", "1X")
- "odd": der EXAKTE "odd"-Wert als Float (z. B. 1.85)
Falls keine passende Betano-Quote vorhanden: bet_id=null, bet_value=null, odd=null

Antworte am Ende AUSSCHLIESSLICH mit validem JSON – kein Text davor oder danach:

{
  "picks": [
    {
      "market": "Beschreibung des Wettmarkts auf Deutsch",
      "pick": "Konkrete Empfehlung",
      "bet_id": 1,
      "bet_value": "Home",
      "odd": 1.85,
      "confidence": "niedrig | mittel | hoch",
      "reasoning": "1-2 Sätze Begründung auf Deutsch (inkl. Web-Recherche-Erkenntnisse)",
      "result": null
    }
  ],
  "top_scorer": {
    "player_name": "Vollständiger Name oder 'Unbekannt'",
    "team": "Heimteam oder Auswärtsteam",
    "reasoning": "1 Satz Begründung auf Deutsch"
  },
  "summary": "2-3 Sätze Gesamteinschätzung auf Deutsch (inkl. wichtigste Recherche-Erkenntnisse)"
}

Regeln:
- Recherchiere ZUERST, dann picks erstellen
- Exakt 5 Picks, verschiedene Märkte bevorzugen
- Nutze ALLE Daten: eigene Recherche + Elo, Form, Torwahrscheinlichkeit, Verletzungen, API-Prediction, Quoten
- Confidence 'hoch' nur wenn mehrere Indikatoren (inkl. Recherche) übereinstimmen
- result IMMER als null setzen
- Kein Text außerhalb des abschließenden JSON"""


WEB_SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search"}


def _extract_final_text(content: list) -> str:
    """Extract the last text block from Claude's response content."""
    text_blocks = [b for b in content if hasattr(b, "text")]
    if not text_blocks:
        raise ValueError("No text in Claude response")
    return text_blocks[-1].text.strip()


def _run_agentic_loop(
    client: anthropic.Anthropic,
    user_message: str,
    system_prompt: str | None = None,
    max_tokens: int = 2500,
) -> str:
    """
    Run Claude with web search in an agentic loop.
    Claude searches the web autonomously, then returns final JSON.
    Falls back to plain call if web search is unavailable.
    system_prompt defaults to SYSTEM_PROMPT if not provided.
    """
    active_prompt = system_prompt or SYSTEM_PROMPT
    messages: list[dict] = [{"role": "user", "content": user_message}]
    max_iterations = 12

    for iteration in range(max_iterations):
        try:
            response = client.beta.messages.create(
                model=MODEL,
                max_tokens=max_tokens,
                system=active_prompt,
                tools=[WEB_SEARCH_TOOL],
                messages=messages,
                betas=["web-search-2025-03-05"],
            )
        except Exception as e:
            if iteration == 0:
                # Web search unavailable – fall back to plain call
                logger.warning("Web search unavailable, falling back: %s", e)
                response = client.messages.create(
                    model=MODEL,
                    max_tokens=max_tokens,
                    system=active_prompt,
                    messages=messages,
                )
                return _extract_final_text(response.content)
            raise

        logger.debug("AI loop iter=%d stop_reason=%s blocks=%d",
                     iteration, response.stop_reason, len(response.content))

        if response.stop_reason == "end_turn":
            return _extract_final_text(response.content)

        # Tool use (web_search): add assistant turn and continue
        # For server-side tools, Anthropic handles execution – we just pass content back
        messages.append({"role": "assistant", "content": response.content})

        # Build tool_result placeholders for any tool_use blocks
        # (server-side web_search results are already embedded in content by Anthropic)
        tool_results = []
        for block in response.content:
            block_type = getattr(block, "type", None)
            if block_type == "tool_use":
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": "Search executed by server.",
                })

        if tool_results:
            messages.append({"role": "user", "content": tool_results})

    raise RuntimeError(f"Agentic loop exceeded {max_iterations} iterations")


def _enrich_pick_with_odd(pick: dict, odds_by_bet_id: dict[int, list]) -> dict:
    """Validate/correct the odd value from DB to avoid Claude hallucinating quotes."""
    bet_id = pick.get("bet_id")
    bet_value = pick.get("bet_value")

    if bet_id is None or bet_value is None:
        pick["odd"] = None
        return pick

    values = odds_by_bet_id.get(int(bet_id), [])
    matched = next((v for v in values if str(v.get("value", "")).strip() == str(bet_value).strip()), None)
    if matched:
        pick["odd"] = _parse_odd(matched.get("odd"))
    else:
        # Claude referenced a non-existent value – set odd to None
        pick["odd"] = None
        logger.warning("AI pick bet_id=%s bet_value=%r not found in DB odds", bet_id, bet_value)

    pick["result"] = pick.get("result")  # keep null
    return pick


async def generate_ai_picks(db: AsyncSession, fixture_id: int, force: bool = False) -> dict:
    """Generate AI picks for a fixture and store them. Returns the picks dict."""

    if not settings.anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY not configured")

    # Return cached if not forced
    if not force:
        existing = (await db.execute(
            select(FixtureAiPick).where(FixtureAiPick.fixture_id == fixture_id)
        )).scalar_one_or_none()
        if existing:
            return {
                "fixture_id": fixture_id,
                "picks": existing.picks,
                "top_scorer": existing.top_scorer,
                "summary": existing.summary,
                "model_version": existing.model_version,
                "generated_at": existing.generated_at.isoformat(),
                "cached": True,
            }

    data = await _gather_fixture_data(db, fixture_id)
    if not data:
        raise ValueError(f"Fixture {fixture_id} not found")

    status = data.get("fixture", {}).get("status", "")
    if status in ("FT", "AET", "PEN"):
        raise ValueError(f"Fixture {fixture_id} ist bereits beendet ({status}) – keine KI-Picks generierbar.")

    # Extract odds lookup for enrichment/validation after Claude responds
    odds_by_bet_id: dict[int, list] = {
        int(k): v["values"] for k, v in data.get("betano_odds", {}).items()
    }

    home_name = data.get("home", {}).get("name", "Heimteam")
    away_name = data.get("away", {}).get("name", "Auswärtsteam")
    league_name = data.get("league", {}).get("name", "Liga")
    kickoff = data.get("fixture", {}).get("kickoff_utc", "")[:10]

    user_message = (
        f"Analysiere das Spiel {home_name} vs. {away_name} ({league_name}, {kickoff}).\n\n"
        f"SCHRITT 1: Recherchiere jetzt aktuell:\n"
        f"- Verletzungen/Sperren bei {home_name} und {away_name} (letzte 48-72h)\n"
        f"- Letzte Spielergebnisse beider Teams\n"
        f"- Aktuelle Neuigkeiten die das Spiel beeinflussen könnten\n"
        f"- Mögliche Torschützen (Top-Stürmer, aktuelle Form)\n\n"
        f"SCHRITT 2: Erstelle auf Basis der Recherche + folgender Statistikdaten exakt 5 Picks.\n"
        f"Referenziere für jeden Pick die passende Quote aus 'betano_odds'.\n\n"
        f"{json.dumps(data, ensure_ascii=False, indent=2)}"
    )

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    # Agentic call: Claude searches the web for current news, then returns JSON
    raw = _run_agentic_loop(client, user_message)
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rstrip("`").strip()

    parsed = json.loads(raw)

    # Enrich each pick: validate odd against DB, ensure result=null
    picks = [
        _enrich_pick_with_odd(pick, odds_by_bet_id)
        for pick in parsed.get("picks", [])
    ]
    top_scorer = parsed.get("top_scorer")
    summary = parsed.get("summary")

    now = datetime.utcnow()
    stmt = pg_insert(FixtureAiPick).values(
        fixture_id=fixture_id,
        picks=picks,
        top_scorer=top_scorer,
        summary=summary,
        model_version=MODEL,
        generated_at=now,
        updated_at=now,
    ).on_conflict_do_update(
        constraint="uq_fixture_ai_picks_fixture_id",
        set_={"picks": picks, "top_scorer": top_scorer, "summary": summary,
              "model_version": MODEL, "updated_at": now},
    )
    await db.execute(stmt)
    await db.commit()

    logger.info("AI picks generated for fixture %s (%d picks)", fixture_id, len(picks))
    return {
        "fixture_id": fixture_id,
        "picks": picks,
        "top_scorer": top_scorer,
        "summary": summary,
        "model_version": MODEL,
        "generated_at": now.isoformat(),
        "cached": False,
    }
