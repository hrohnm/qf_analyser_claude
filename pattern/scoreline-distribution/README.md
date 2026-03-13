# Pattern: Scoreline Distribution

Status: `draft`

## Zweck

Berechnung der vollständigen Ergebnismatrix (0-0, 1-0, 0-1, 1-1, 2-0, ...) für ein bevorstehendes Spiel über das unabhängige Poisson-Modell. Die Verteilung ermöglicht die direkte Ableitung aller relevanten Wettmärkte und macht den wahrscheinlichsten genauen Spielausgang transparent.

## Kernidee

Das unabhängige Poisson-Modell nimmt an, dass die Tore beider Teams stochastisch unabhängig voneinander sind und jeweils einer Poisson-Verteilung folgen. Aus den erwarteten Torwerten λ_home und λ_away (geliefert von `goal-probability-weighted` oder `match-result-probability`) lässt sich für jede mögliche Kombination (i Tore Heim, j Tore Auswärts) eine exakte Wahrscheinlichkeit berechnen:

```
P(Heim=i, Away=j) = Poisson(i; λ_home) × Poisson(j; λ_away)

Poisson(k; λ) = (e^-λ × λ^k) / k!
```

Die Matrix wird für i, j ∈ {0, 1, 2, 3, 4, 5, 6+} berechnet. Der Resttopf `6+` enthält die Restwahrscheinlichkeit.

### Aggregationen aus der Matrix

Alle Marktwahrscheinlichkeiten lassen sich direkt aus der Matrix lesen:

| Markt          | Berechnung                                      |
|----------------|-------------------------------------------------|
| Heimsieg       | Σ P(i,j) für i > j                             |
| Unentschieden  | Σ P(i,j) für i = j                             |
| Auswärtssieg   | Σ P(i,j) für i < j                             |
| Over 1,5       | 1 - P(0,0) - P(0,1) - P(1,0)                  |
| Over 2,5       | 1 - Σ P(i,j) für i+j ≤ 2                      |
| Over 3,5       | 1 - Σ P(i,j) für i+j ≤ 3                      |
| BTTS           | Σ P(i,j) für i ≥ 1 und j ≥ 1                  |
| Clean Sheet H  | Σ P(i,0) für alle i                            |
| Clean Sheet A  | Σ P(0,j) für alle j                            |

### Korrelations-Korrektur (optional)

Das reine unabhängige Poisson-Modell unterschätzt leicht die Unentschieden-Wahrscheinlichkeit. Eine Dixon-Coles-Korrektur kann für kleine Scorelines (0-0, 1-0, 0-1, 1-1) angewendet werden:

```
P*(0,0) = P(0,0) × (1 - λ_home × λ_away × rho)
P*(1,0) = P(1,0) × (1 + λ_away × rho)
P*(0,1) = P(0,1) × (1 + λ_home × rho)
P*(1,1) = P(1,1) × (1 - rho)

# rho ≈ -0.13 (empirisch kalibriert, Standardwert)
# Renormalisierung nach der Korrektur erforderlich
```

## Output-Felder

```json
{
  "fixture_id": 12345,
  "lambda_home": 1.72,
  "lambda_away": 1.18,
  "matrix": {
    "0-0": 0.052,
    "1-0": 0.090,
    "2-0": 0.077,
    "3-0": 0.044,
    "0-1": 0.061,
    "1-1": 0.106,
    "2-1": 0.091,
    "3-1": 0.052,
    "0-2": 0.036,
    "1-2": 0.063,
    "2-2": 0.054,
    "3-2": 0.031,
    "0-3": 0.014,
    "1-3": 0.025,
    "2-3": 0.021,
    "3-3": 0.012
  },
  "top_scorelines": [
    {"scoreline": "1-1", "probability": 0.106},
    {"scoreline": "1-0", "probability": 0.090},
    {"scoreline": "2-1", "probability": 0.091}
  ],
  "market_probs": {
    "p_home_win": 0.48,
    "p_draw": 0.27,
    "p_away_win": 0.25,
    "p_btts": 0.52,
    "p_over_1_5": 0.81,
    "p_over_2_5": 0.58,
    "p_over_3_5": 0.31,
    "p_clean_sheet_home": 0.17,
    "p_clean_sheet_away": 0.24
  },
  "dixon_coles_applied": true,
  "computed_at": "2026-03-10T12:00:00Z"
}
```

## Datenbasis

- `fixture_goal_probability` (λ_home, λ_away aus `goal-probability-weighted`)
- Optional: `match-result-probability` (falls bereits aggregierte λ-Werte verfügbar)

## Abhängigkeiten zu anderen Pattern

```
goal-probability-weighted ──► scoreline-distribution
                               │
                               ├──► match-result-probability (1X2, O/U, BTTS)
                               ├──► value-bet-identifier (Markt-Wahrscheinlichkeiten)
                               └──► ai-match-picks (vollständige Matrix als Kontext)
```

## Nutzen für Wettscheine/Analyse

- **Correct Score Markt**: Die Matrix gibt direkt die wahrscheinlichsten Ergebnisse an – nützlich für Correct-Score-Wetten mit oft hohen Quoten
- **Half-Time/Full-Time**: Durch Split-λ (1./2. Halbzeit) theoretisch erweiterbar
- **Handicap-Markt**: Aus der Matrix lassen sich Asian-Handicap-Wahrscheinlichkeiten direkt ableiten
- **Visualisierung**: Die Matrix eignet sich als Heatmap auf der Match-Detailseite
- **Vollständigkeit**: Alle Einzelmarkt-Wahrscheinlichkeiten stammen aus derselben konsistenten Berechnung
