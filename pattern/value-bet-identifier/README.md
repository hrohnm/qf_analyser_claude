# Pattern: Value Bet Identifier

Status: `draft`

## Zweck

Vergleich der intern berechneten Modell-Wahrscheinlichkeiten mit den impliziten Wahrscheinlichkeiten der Buchmacher-Quoten, um statistisch vorteilhafte Wetten (Value Bets) zu identifizieren. Wetten mit positivem Expected Value (EV > 0) werden priorisiert und mit einer Edge-Stärke bewertet.

## Kernidee

Jede Buchmacher-Quote enthält eine implizite Wahrscheinlichkeit. Diese enthält auch die Marge des Buchmachers (Vig/Overround). Wenn unser Modell eine höhere Wahrscheinlichkeit für ein Ereignis berechnet als der Buchmaker impliziert, liegt ein positiver Edge vor:

```
p_implied = 1 / quote_dezimal
p_model   = Modell-Wahrscheinlichkeit (aus match-result-probability)

edge = p_model - p_implied_fair
ev   = p_model × (quote_dezimal - 1) - (1 - p_model)
```

### Vig-Bereinigung (fair probability)

Buchmacher erheben eine Marge über alle Outcomes hinweg. Für den 1X2-Markt:

```
overround = p_implied_home + p_implied_draw + p_implied_away
p_fair_home = p_implied_home / overround
p_fair_draw = p_implied_draw / overround
p_fair_away = p_implied_away / overround
```

Nach Vig-Bereinigung entspricht die faire Wahrscheinlichkeit dem, was der Buchmaker tatsächlich erwartet. Erst dann ist der Vergleich mit unserem Modell sinnvoll.

### Value-Schwellen

| Stufe         | Edge-Bedingung               | Interpretation                              |
|---------------|------------------------------|---------------------------------------------|
| `no_value`    | edge < 0.02                  | Kein oder marginaler Vorteil                |
| `marginal`    | 0.02 ≤ edge < 0.05           | Leichter Vorteil, mit Vorsicht prüfen       |
| `value`       | 0.05 ≤ edge < 0.10           | Klarer Value, empfehlenswert                |
| `strong_value`| edge ≥ 0.10                  | Starker Edge, hohe Priorität                |

### Unterstützte Märkte

Das Pattern wertet alle verfügbaren Odds-Märkte aus:

- `1X2` (Heimsieg / Unentschieden / Auswärtssieg)
- `Over/Under 1,5` / `Over/Under 2,5` / `Over/Under 3,5`
- `BTTS` (Beide Teams treffen: Ja / Nein)
- `Double Chance` (1X / X2 / 12)
- `Asian Handicap` (falls verfügbar)

### Kelly-Kriterium (optional, für Bankroll-Management)

Für priorisierte Value-Bets kann der empfohlene Einsatz via Kelly berechnet werden:

```
kelly_fraction = (edge × (quote - 1) - (1 - p_model)) / (quote - 1)
empfohlener_einsatz = bankroll × kelly_fraction × kelly_faktor
# kelly_faktor = 0.25 (Quarter Kelly, konservativ)
```

### Confidence-Filter

Value-Bets werden nur ausgegeben, wenn `match-result-probability.confidence` ≥ `medium`. Bei `low`-Confidence werden Ergebnisse als nicht actionable markiert.

## Output-Felder

```json
{
  "fixture_id": 12345,
  "computed_at": "2026-03-10T12:00:00Z",
  "model_confidence": "high",
  "value_bets": [
    {
      "market": "1X2",
      "selection": "home_win",
      "p_model": 0.52,
      "p_implied_raw": 0.44,
      "p_implied_fair": 0.46,
      "edge": 0.06,
      "quote": 2.15,
      "ev": 0.118,
      "value_tier": "value",
      "kelly_fraction": 0.056,
      "bookmaker": "Betano"
    },
    {
      "market": "over_under",
      "selection": "over_2_5",
      "p_model": 0.61,
      "p_implied_raw": 0.50,
      "p_implied_fair": 0.53,
      "edge": 0.08,
      "quote": 1.90,
      "ev": 0.149,
      "value_tier": "value",
      "kelly_fraction": 0.084,
      "bookmaker": "Betano"
    }
  ],
  "all_markets": [
    {
      "market": "1X2",
      "selection": "draw",
      "p_model": 0.26,
      "p_implied_fair": 0.28,
      "edge": -0.02,
      "value_tier": "no_value"
    }
  ],
  "overround_1x2": 1.068,
  "best_value_bet": {
    "market": "over_under",
    "selection": "over_2_5",
    "ev": 0.149
  }
}
```

## Datenbasis

- `fixture_odds` (Buchmacher-Quoten, mind. `fixture_id`, `market`, `selection`, `quote_decimal`)
- `fixture_result_probability` (Modell-Wahrscheinlichkeiten aus `match-result-probability`)

## Abhängigkeiten zu anderen Pattern

```
match-result-probability ──┐
                            ├──► value-bet-identifier
fixture_odds (Betano)      ──┘
```

Voraussetzung: `match-result-probability` muss vor diesem Pattern berechnet worden sein.

## Nutzen für Wettscheine/Analyse

- **Kernfunktion des Projekts**: Dieses Pattern ist die direkte Schnittstelle zwischen Modell und Wettmarkt
- **Selektivität**: Nicht jedes Spiel hat Value-Bets – das Pattern hilft, die wenigen profitablen Gelegenheiten herauszufiltern
- **Transparenz**: Edge und EV sind explizit ausgewiesen, nicht nur eine subjektive Empfehlung
- **Bankroll Management**: Kelly-Fraktionen ermöglichen diszipliniertes Einsatz-Sizing
- **Multi-Markt**: Nicht nur 1X2, sondern alle verfügbaren Märkte werden gescreent
- **Input für KI**: Value-Bets werden als priorisierte Kandidaten an `ai-match-picks` übergeben
