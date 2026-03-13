# Pattern: AI Match Picks

Status: `draft`

## Zweck

Claude (Anthropic) generiert auf Basis aller vorhandenen Spieldaten
5 strukturierte Wett-Empfehlungen und einen potenziellen Torschützen.

## Kernidee

Claude erhält als Kontext:
- Fixture-Basisdaten (Teams, Liga, Spieltag, Anstoß)
- Unsere Pattern: Elo, Form, Torwahrscheinlichkeit, Gegentorwahrscheinlichkeit, Match-Lines
- API-Football: Siegchance %, Comparison-Block, Last-5, Saison-Stats
- Verletzungen + Impact-Scores
- Betano-Quoten (falls vorhanden)

Claude gibt strukturiertes JSON zurück:

```json
{
  "picks": [
    {
      "market": "Ergebnis",
      "pick": "Heimsieg",
      "confidence": "hoch",
      "reasoning": "..."
    },
    ...
  ],
  "top_scorer": {
    "player_name": "Max Mustermann",
    "team": "Heimteam",
    "reasoning": "..."
  },
  "summary": "Kurze Gesamteinschätzung des Spiels"
}
```

## Output-Felder pro Pick

- `market`: Wettmarkt (z. B. „Ergebnis", „Über 2,5 Tore", „Beide Teams treffen", „Halbzeit/Endstand", „Handicap")
- `pick`: Konkrete Empfehlung
- `confidence`: `niedrig` | `mittel` | `hoch`
- `reasoning`: 1–2 Sätze Begründung

## Modell

`claude-sonnet-4-6` (aktuellstes Sonnet-Modell, gutes Preis-Leistungs-Verhältnis)

## Datenbasis

- `fixtures`, `fixture_statistics`, `fixture_goal_probability`
- `team_elo_snapshot`, `team_form_snapshot`
- `fixture_predictions` (API-Football)
- `fixture_injuries`, `fixture_injury_impacts`
- `fixture_odds` (Betano)

## Speicherung

Tabelle `fixture_ai_picks`:
- `fixture_id`
- `picks` (JSON-Array mit 5 Picks)
- `top_scorer` (JSON-Objekt)
- `summary` (Text)
- `model_version` (z. B. `claude-sonnet-4-6`)
- `generated_at`
