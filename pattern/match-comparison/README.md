# Pattern: Match Comparison

Status: `draft`

## Zweck

Eigene Berechnung der 7 Vergleichsdimensionen, die API-Football als `comparison`-Block liefert –
damit wir unsere Modellwerte direkt mit der externen Vorhersage vergleichen können.

## Dimensionen (analog API-Football)

| Dimension     | API-Football Quelle                   | Unsere Quelle                                           |
|---------------|---------------------------------------|---------------------------------------------------------|
| `form`        | Formgewichteter Score (intern)        | `team_form_snapshot.form_score` (Heim vs. Auswärts-Scope) |
| `att`         | Angriffsstärke (intern)               | Tore/Spiel + xG/Spiel + Schüsse aufs Tor/Spiel          |
| `def`         | Defensivstärke (intern)               | Gegentore/Spiel + xG-gegen + Schüsse zugelassen          |
| `poisson`     | Poisson-Gewinner-Wahrscheinlichkeit   | Aus unseren `fixture_goal_probability` λ-Werten          |
| `h2h`         | Historische Direktduelle              | Letzte 10 H2H-Fixtures aus der DB                        |
| `goals`       | Torziel-Wahrscheinlichkeit            | p_ge_1_goal aus `fixture_goal_probability`               |
| `total`       | Gewichtete Gesamtwertung              | Gewichteter Schnitt aller 6 Dimensionen                  |

Alle Werte werden als Prozentwert des Heimteams (0–100) ausgegeben,
`away = 100 - home` (da immer zwei Teams gegeneinander stehen).

## Output

Pro Fixture ein Dict mit 7 Schlüsseln:

```json
{
  "form":    {"home": 67.5, "away": 32.5},
  "att":     {"home": 58.2, "away": 41.8},
  "def":     {"home": 44.1, "away": 55.9},
  "poisson": {"home": 61.3, "away": 38.7},
  "h2h":     {"home": 40.0, "away": 60.0},
  "goals":   {"home": 55.0, "away": 45.0},
  "total":   {"home": 54.4, "away": 45.6}
}
```

## Verwendung

- Direkter Vergleich mit API-Football `comparison` Block im Spinnendiagramm
- Basis-Daten für `ai-match-picks`
- Standalone in der Match-Detailseite als „Eigener Vergleich"
