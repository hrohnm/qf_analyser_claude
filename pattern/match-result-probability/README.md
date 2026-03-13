# Pattern: Match Result Probability

Status: `draft`

## Zweck

Berechnung finaler Wahrscheinlichkeiten für alle relevanten Wettmärkte eines Spiels (1X2, BTTS, Over/Under) als gewichtete Kombination aller bestehenden Sub-Pattern. Dieses Pattern ist das zentrale Aggregations-Pattern und liefert die Grundlage für Value-Bet-Identifikation und KI-Picks.

## Kernidee

Kein einzelnes Sub-Pattern ist allein ausreichend – Elo misst langfristige Stärke, Form kurzfristige Verfassung, Goal-Probability die Torgefahr, H2H-Matchup historische Direktduelle, Home-Advantage-Calibration den Team-spezifischen Feldvorteil und Injury-Impact aktuelle Ausfälle. Dieses Pattern bündelt alle Signale in eine finale Wahrscheinlichkeitsverteilung.

### Aggregationsgewichte

Die rohen Modellwahrscheinlichkeiten werden aus mehreren Quellen zusammengesetzt:

| Quelle                          | Gewicht | Begründung                                      |
|---------------------------------|---------|-------------------------------------------------|
| `goal-probability-weighted`     | 35 %    | Stärkstes direktes Torkraft-Signal              |
| `team-elo` (Elo-Differenz)      | 25 %    | Robust, saisonweit stabil                       |
| `team-current-form`             | 20 %    | Kurzfristiger Trend, letzten 5–10 Spiele        |
| `h2h-matchup`                   | 10 %    | Direktduelle, psychologischer Faktor            |
| `home-advantage-calibration`    |  5 %    | Team-spezifischer Heimvorteil-Faktor            |
| `injury-impact-player`          |  5 %    | Abzug bei kritischen Ausfällen                  |

### 1X2-Ableitung

Aus den aggregierten λ-Werten (Heim/Auswärts) wird über die bivariate Poisson-Verteilung eine vollständige Ergebnismatrix (→ `scoreline-distribution`) berechnet. Die 1X2-Wahrscheinlichkeiten ergeben sich durch Aufsummierung:

```
p_home_win = Σ P(home=i, away=j) für i > j
p_draw     = Σ P(home=i, away=j) für i = j
p_away_win = Σ P(home=i, away=j) für i < j
```

### BTTS-Ableitung

```
p_btts = p_ge_1_home × p_ge_1_away × korrelations_abschlag
```

Der `korrelations_abschlag` (Standard: 0.95) korrigiert die positive Korrelation offensiver Partien (beide Teams taktisch offensiv → beide wahrscheinlicher scorend).

### Over/Under-Ableitung

```
lambda_total = lambda_home + lambda_away
p_over_2_5  = 1 - Poisson_CDF(lambda_total, k=2)
p_over_1_5  = 1 - Poisson_CDF(lambda_total, k=1)
p_over_3_5  = 1 - Poisson_CDF(lambda_total, k=3)
```

### Injury-Adjustment

Wenn `team_injury_impact` > 50 (hoher Ausfall-Score), wird das λ des betroffenen Teams skaliert:

```
lambda_adjusted = lambda_base × (1 - injury_reduction_factor)
injury_reduction_factor = team_injury_impact / 1000   # max ~10% Reduktion
```

## Output-Felder

Pro Fixture:

```json
{
  "fixture_id": 12345,
  "p_home_win": 0.48,
  "p_draw": 0.27,
  "p_away_win": 0.25,
  "p_btts": 0.52,
  "p_over_1_5": 0.81,
  "p_over_2_5": 0.58,
  "p_over_3_5": 0.31,
  "lambda_home": 1.72,
  "lambda_away": 1.18,
  "confidence": "high",
  "model_version": "1.0",
  "computed_at": "2026-03-10T12:00:00Z",
  "weights_used": {
    "goal_probability": 0.35,
    "elo": 0.25,
    "form": 0.20,
    "h2h": 0.10,
    "home_advantage": 0.05,
    "injury_impact": 0.05
  }
}
```

### Confidence-Stufen

| Stufe    | Kriterium                                                    |
|----------|--------------------------------------------------------------|
| `high`   | Alle 6 Sub-Pattern verfügbar, min. 10 Historien-Fixtures     |
| `medium` | Mindestens 4 Sub-Pattern verfügbar, min. 5 Historien-Fixtures|
| `low`    | Weniger als 4 Sub-Pattern oder sehr wenige Historien-Daten   |

## Datenbasis

- `fixture_goal_probability` (λ-Werte aus `goal-probability-weighted`)
- `team_elo_snapshot` (aus `team-elo`)
- `team_form_snapshot` (aus `team-current-form`)
- `fixture_h2h_matchup` (aus `h2h-matchup`)
- `team_home_advantage` (aus `home-advantage-calibration`)
- `fixture_injury_impacts` (aus `injury-impact-player`)

## Abhängigkeiten

Dieses Pattern ist ein reines Aggregations-Pattern – es liest ausschließlich aus den Output-Tabellen anderer Pattern:

```
goal-probability-weighted  ──┐
team-elo                   ──┤
team-current-form          ──┼──► match-result-probability
h2h-matchup                ──┤
home-advantage-calibration ──┤
injury-impact-player       ──┘
```

Empfohlene Ausführungsreihenfolge beim Sync:
1. Alle Sub-Pattern berechnen
2. `match-result-probability` als letztes ausführen

## Nutzen für Wettscheine/Analyse

- **Direkte Wett-Grundlage**: p_home_win / p_draw / p_away_win sind direkt mit Buchmacher-Quoten vergleichbar (→ `value-bet-identifier`)
- **BTTS-Markt**: p_btts direkt verwendbar
- **Over/Under**: p_over_1_5 / p_over_2_5 / p_over_3_5 direkt verwendbar
- **KI-Input**: Dient als primärer Zahlen-Input für `ai-match-picks`
- **Konsistenz**: Alle Wettmärkte stammen aus demselben λ-Modell → keine widersprüchlichen Empfehlungen
