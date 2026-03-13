"""
GPT-4o match analysis service.

Gathers all available fixture data and asks ChatGPT for:
  - A detailed text analysis of the match (~300-400 words, German)
  - 5 concrete betting tips with market, pick, confidence, reasoning

Response schema:
{
  "analysis": "...",
  "betting_tips": [
    {
      "tip_nr": 1,
      "market": "Siegerwette",
      "pick": "Heimsieg",
      "confidence": "hoch",
      "reasoning": "..."
    },
    ...
  ]
}
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.fixture import Fixture
from app.models.fixture_gpt_analysis import FixtureGptAnalysis
from app.models.fixture_goal_probability import FixtureGoalProbability
from app.models.fixture_h2h import FixtureH2H
from app.models.fixture_injury import FixtureInjury
from app.models.fixture_injury_impact import FixtureInjuryImpact
from app.models.fixture_match_result_probability import FixtureMatchResultProbability
from app.models.fixture_odds import FixtureOdds
from app.models.fixture_prediction import FixturePrediction
from app.models.fixture_scoreline_distribution import FixtureScorelineDistribution
from app.models.fixture_value_bet import FixtureValueBet
from app.models.league import League
from app.models.team import Team
from app.models.team_elo_snapshot import TeamEloSnapshot
from app.models.team_form_snapshot import TeamFormSnapshot

logger = logging.getLogger(__name__)

GPT_MODEL = "gpt-4o"
BETANO_ID = 32

BET_ID_LABELS = {
    1:   "Match Winner (1X2) – Home / Draw / Away",
    5:   "Goals Over/Under (gesamt) – 'Over X.X' / 'Under X.X'",
    12:  "Doppelchance – 1X / X2 / 12",
    16:  "Tore Heimteam – 'Over X.X' / 'Under X.X'",
    17:  "Tore Auswärtsteam – 'Over X.X' / 'Under X.X'",
    8:   "Beide Teams treffen – Yes / No",
}


def _pf(v) -> float | None:
    return float(v) if v is not None else None


async def _gather_data(db: AsyncSession, fixture_id: int) -> dict[str, Any]:
    """Collect all relevant fixture data into a structured dict."""
    fix = (await db.execute(select(Fixture).where(Fixture.id == fixture_id))).scalar_one_or_none()
    if not fix:
        raise ValueError(f"Fixture {fixture_id} nicht gefunden")

    home_team = (await db.execute(select(Team).where(Team.id == fix.home_team_id))).scalar_one_or_none()
    away_team = (await db.execute(select(Team).where(Team.id == fix.away_team_id))).scalar_one_or_none()
    league = (await db.execute(select(League).where(League.id == fix.league_id))).scalar_one_or_none()

    home_name = home_team.name if home_team else f"Team {fix.home_team_id}"
    away_name = away_team.name if away_team else f"Team {fix.away_team_id}"

    # Elo
    elo_rows = (await db.execute(
        select(TeamEloSnapshot).where(
            TeamEloSnapshot.league_id == fix.league_id,
            TeamEloSnapshot.season_year == fix.season_year,
            TeamEloSnapshot.team_id.in_([fix.home_team_id, fix.away_team_id]),
        )
    )).scalars().all()
    elo_map = {e.team_id: e for e in elo_rows}
    home_elo = elo_map.get(fix.home_team_id)
    away_elo = elo_map.get(fix.away_team_id)

    # Form (home/away scope)
    form_rows = (await db.execute(
        select(TeamFormSnapshot).where(
            TeamFormSnapshot.league_id == fix.league_id,
            TeamFormSnapshot.season_year == fix.season_year,
            TeamFormSnapshot.window_size == 5,
            TeamFormSnapshot.team_id.in_([fix.home_team_id, fix.away_team_id]),
            TeamFormSnapshot.scope.in_(["home", "away"]),
        )
    )).scalars().all()
    form_map = {(f.team_id, f.scope): f for f in form_rows}
    home_form = form_map.get((fix.home_team_id, "home"))
    away_form = form_map.get((fix.away_team_id, "away"))

    # Goal probability
    gp_rows = (await db.execute(
        select(FixtureGoalProbability).where(FixtureGoalProbability.fixture_id == fixture_id)
    )).scalars().all()
    gp_home = next((r for r in gp_rows if r.team_id == fix.home_team_id), None)
    gp_away = next((r for r in gp_rows if r.team_id == fix.away_team_id), None)

    # Match Result Probability
    mrp = (await db.execute(
        select(FixtureMatchResultProbability).where(FixtureMatchResultProbability.fixture_id == fixture_id)
    )).scalar_one_or_none()

    # Scoreline Distribution
    sd = (await db.execute(
        select(FixtureScorelineDistribution).where(FixtureScorelineDistribution.fixture_id == fixture_id)
    )).scalar_one_or_none()

    # H2H
    h2h = (await db.execute(
        select(FixtureH2H).where(FixtureH2H.fixture_id == fixture_id)
    )).scalar_one_or_none()

    # Injuries + impacts
    injuries = (await db.execute(
        select(FixtureInjury).where(FixtureInjury.fixture_id == fixture_id)
    )).scalars().all()
    impacts = (await db.execute(
        select(FixtureInjuryImpact).where(FixtureInjuryImpact.fixture_id == fixture_id)
    )).scalars().all()
    impact_by_player = {i.player_id: i for i in impacts if i.player_id}
    home_impact_total = round(sum(float(i.impact_score) for i in impacts if i.team_id == fix.home_team_id), 1)
    away_impact_total = round(sum(float(i.impact_score) for i in impacts if i.team_id == fix.away_team_id), 1)

    # API-Football prediction
    pred = (await db.execute(
        select(FixturePrediction).where(FixturePrediction.fixture_id == fixture_id)
    )).scalar_one_or_none()

    # Value bets
    vb_rows = (await db.execute(
        select(FixtureValueBet)
        .where(FixtureValueBet.fixture_id == fixture_id)
        .order_by(FixtureValueBet.edge.desc())
    )).scalars().all()

    # Betano odds
    odds_rows = (await db.execute(
        select(FixtureOdds).where(
            FixtureOdds.fixture_id == fixture_id,
            FixtureOdds.bookmaker_id == BETANO_ID,
        )
    )).scalars().all()
    odds_by_bet_id = {o.bet_id: o.values for o in odds_rows}
    available_odds = {
        str(bet_id): {"label": label, "values": odds_by_bet_id[bet_id]}
        for bet_id, label in BET_ID_LABELS.items()
        if bet_id in odds_by_bet_id
    }

    return {
        "fixture": {
            "id": fix.id,
            "kickoff_utc": fix.kickoff_utc.isoformat() if fix.kickoff_utc else None,
            "matchday": fix.matchday,
            "venue": fix.venue_name,
        },
        "league": {
            "name": league.name if league else None,
            "country": league.country if league else None,
        },
        "home": {
            "name": home_name,
            "elo": {
                "overall": _pf(home_elo.elo_overall) if home_elo else None,
                "home": _pf(home_elo.elo_home) if home_elo else None,
                "tier": home_elo.strength_tier if home_elo else None,
                "trend_last5": _pf(home_elo.elo_delta_last_5) if home_elo else None,
            },
            "form": {
                "score": _pf(home_form.form_score) if home_form else None,
                "trend": home_form.form_trend if home_form else None,
                "bucket": home_form.form_bucket if home_form else None,
            },
            "goal_prob": {
                "p_scores": _pf(gp_home.p_ge_1_goal) if gp_home else None,
                "p_2plus": _pf(gp_home.p_ge_2_goals) if gp_home else None,
                "lambda": _pf(gp_home.lambda_weighted) if gp_home else None,
            },
            "injury_impact_total": home_impact_total,
            "injuries": [
                {
                    "player": i.player_name,
                    "type": i.injury_type,
                    "impact_bucket": impact_by_player[i.player_id].impact_bucket if i.player_id and i.player_id in impact_by_player else None,
                }
                for i in injuries if i.team_id == fix.home_team_id
            ],
        },
        "away": {
            "name": away_name,
            "elo": {
                "overall": _pf(away_elo.elo_overall) if away_elo else None,
                "away": _pf(away_elo.elo_away) if away_elo else None,
                "tier": away_elo.strength_tier if away_elo else None,
                "trend_last5": _pf(away_elo.elo_delta_last_5) if away_elo else None,
            },
            "form": {
                "score": _pf(away_form.form_score) if away_form else None,
                "trend": away_form.form_trend if away_form else None,
                "bucket": away_form.form_bucket if away_form else None,
            },
            "goal_prob": {
                "p_scores": _pf(gp_away.p_ge_1_goal) if gp_away else None,
                "p_2plus": _pf(gp_away.p_ge_2_goals) if gp_away else None,
                "lambda": _pf(gp_away.lambda_weighted) if gp_away else None,
            },
            "injury_impact_total": away_impact_total,
            "injuries": [
                {
                    "player": i.player_name,
                    "type": i.injury_type,
                    "impact_bucket": impact_by_player[i.player_id].impact_bucket if i.player_id and i.player_id in impact_by_player else None,
                }
                for i in injuries if i.team_id == fix.away_team_id
            ],
        },
        "match_result_probability": {
            "p_home_win": _pf(mrp.p_home_win) if mrp else None,
            "p_draw": _pf(mrp.p_draw) if mrp else None,
            "p_away_win": _pf(mrp.p_away_win) if mrp else None,
            "p_btts": _pf(mrp.p_btts) if mrp else None,
            "p_over_15": _pf(mrp.p_over_15) if mrp else None,
            "p_over_25": _pf(mrp.p_over_25) if mrp else None,
            "p_over_35": _pf(mrp.p_over_35) if mrp else None,
            "confidence": _pf(mrp.confidence) if mrp else None,
        } if mrp else None,
        "scoreline": {
            "most_likely": sd.most_likely_score if sd else None,
            "most_likely_prob": _pf(sd.most_likely_score_prob) if sd else None,
            "lambda_home": _pf(sd.lambda_home) if sd else None,
            "lambda_away": _pf(sd.lambda_away) if sd else None,
        } if sd else None,
        "h2h": {
            "matches_total": h2h.h2h_matches_total if h2h else None,
            "home_wins": h2h.h2h_home_wins if h2h else None,
            "draws": h2h.h2h_draws if h2h else None,
            "away_wins": h2h.h2h_away_wins if h2h else None,
            "avg_total_goals": _pf(h2h.h2h_avg_total_goals) if h2h else None,
            "btts_rate": _pf(h2h.h2h_btts_rate) if h2h else None,
            "over_25_rate": _pf(h2h.h2h_over_25_rate) if h2h else None,
        } if h2h else None,
        "api_prediction": {
            "winner": pred.winner_name if pred else None,
            "advice": pred.advice if pred else None,
            "percent_home": _pf(pred.percent_home) if pred else None,
            "percent_draw": _pf(pred.percent_draw) if pred else None,
            "percent_away": _pf(pred.percent_away) if pred else None,
            "goals_pred_home": pred.goals_pred_home if pred else None,
            "goals_pred_away": pred.goals_pred_away if pred else None,
        } if pred else None,
        "value_bets": [
            {
                "market": v.market_name,
                "pick": v.bet_value,
                "edge": _pf(v.edge),
                "model_prob": _pf(v.model_prob),
                "bookmaker_odd": _pf(v.bookmaker_odd),
                "tier": v.tier,
            }
            for v in vb_rows
        ],
        "betano_odds": available_odds,
    }


SYSTEM_PROMPT = """\
Du bist ein professioneller Fußball-Analyst und Wettexperte.
Du analysierst Spiele objektiv anhand statistischer Daten und erstellst fundierte Wettempfehlungen.
Antworte ausschließlich auf Deutsch und im JSON-Format.

Deine Antwort muss GENAU diesem JSON-Schema folgen – kein Text davor oder danach:
{
  "analysis": "<Ausführliche Analyse 300-400 Wörter>",
  "betting_tips": [
    {
      "tip_nr": 1,
      "market": "<Marktname z.B. Siegerwette, Über/Unter 2,5 Tore, Doppelchance, BTTS>",
      "pick": "<Genaue Auswahl>",
      "confidence": "<hoch|mittel|niedrig>",
      "reasoning": "<1-2 Sätze Begründung>"
    }
  ]
}

Regeln:
- Analysiere alle gelieferten Daten (Elo, Form, Torwahrscheinlichkeit, Verletzungen, H2H, MRP)
- Gib genau 5 Wett-Tipps aus verschiedenen Märkten
- Confidence: hoch = starkes Signal mehrerer Quellen, mittel = gutes Signal, niedrig = schwaches/widersprüchliches Signal
- Nutze die verfügbaren Betano-Quoten falls vorhanden, um die Attraktivität der Tipps einzuschätzen
- Sei ehrlich: wenn Daten fehlen, erwähne das in der Analyse
"""


async def generate_gpt_analysis(db: AsyncSession, fixture_id: int, force: bool = False) -> dict:
    """Return cached GPT-4o analysis from DB, or generate and persist a new one."""
    # Return cached result unless force-regeneration is requested
    if not force:
        cached = (await db.execute(
            select(FixtureGptAnalysis).where(FixtureGptAnalysis.fixture_id == fixture_id)
        )).scalar_one_or_none()
        if cached:
            fix = (await db.execute(select(Fixture).where(Fixture.id == fixture_id))).scalar_one_or_none()
            from app.models.team import Team
            home_team = (await db.execute(select(Team).where(Team.id == fix.home_team_id))).scalar_one_or_none() if fix else None
            away_team = (await db.execute(select(Team).where(Team.id == fix.away_team_id))).scalar_one_or_none() if fix else None
            from app.models.league import League as LeagueModel
            league = (await db.execute(select(LeagueModel).where(LeagueModel.id == fix.league_id))).scalar_one_or_none() if fix else None
            return {
                "fixture_id": fixture_id,
                "home": home_team.name if home_team else "",
                "away": away_team.name if away_team else "",
                "league": league.name if league else "",
                "analysis": cached.analysis,
                "betting_tips": cached.betting_tips,
                "model": cached.model_version,
                "tokens_used": cached.tokens_used,
                "generated_at": cached.generated_at.isoformat(),
                "cached": True,
            }

    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY ist nicht konfiguriert")

    data = await _gather_data(db, fixture_id)

    home = data["home"]["name"]
    away = data["away"]["name"]
    league = data["league"].get("name", "Unbekannte Liga")

    user_prompt = f"""\
Analysiere das folgende Spiel und erstelle 5 Wett-Tipps:

**{home} vs {away}** ({league})
Anstoß: {data['fixture'].get('kickoff_utc', 'unbekannt')}
Spieltag: {data['fixture'].get('matchday', '?')}

## Statistik-Daten (JSON)

{json.dumps(data, ensure_ascii=False, indent=2)}

Erstelle jetzt deine Analyse und 5 Wett-Tipps im vorgegebenen JSON-Format.
"""

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.chat.completions.create(
        model=GPT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.4,
        max_tokens=2000,
    )

    content = response.choices[0].message.content
    try:
        result = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"GPT hat kein gültiges JSON zurückgegeben: {e}\n{content[:300]}")

    if "analysis" not in result or "betting_tips" not in result:
        raise ValueError(f"GPT-Antwort fehlt Pflichtfelder: {list(result.keys())}")

    tokens_used = response.usage.total_tokens if response.usage else None

    # Persist or update in DB (upsert via delete+insert)
    existing = (await db.execute(
        select(FixtureGptAnalysis).where(FixtureGptAnalysis.fixture_id == fixture_id)
    )).scalar_one_or_none()
    if existing:
        existing.analysis = result["analysis"]
        existing.betting_tips = result["betting_tips"]
        existing.model_version = GPT_MODEL
        existing.tokens_used = tokens_used
        existing.updated_at = datetime.utcnow()
    else:
        db.add(FixtureGptAnalysis(
            fixture_id=fixture_id,
            analysis=result["analysis"],
            betting_tips=result["betting_tips"],
            model_version=GPT_MODEL,
            tokens_used=tokens_used,
        ))
    await db.commit()

    generated_at = existing.generated_at if existing else None

    return {
        "fixture_id": fixture_id,
        "home": home,
        "away": away,
        "league": league,
        "analysis": result["analysis"],
        "betting_tips": result["betting_tips"],
        "model": GPT_MODEL,
        "tokens_used": tokens_used,
        "generated_at": generated_at.isoformat() if generated_at else None,
        "cached": False,
    }
