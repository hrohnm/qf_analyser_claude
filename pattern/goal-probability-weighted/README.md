# Pattern: Goal Probability Weighted

Status: `draft`

## Zweck

Für ein bevorstehendes Spiel die Wahrscheinlichkeit berechnen, dass ein Team

- mindestens 1 Tor,
- mindestens 2 Tore,
- mindestens 3 Tore

erzielt.

Dabei werden historische Tore nicht gleich gewichtet, sondern nach Kontext bewertet.

## Kernidee

Jedes historische Tor bekommt ein Gewicht basierend auf:

1. **Gegnerstärke (Elo)**: Tor gegen starkes Team zählt mehr.
2. **Defensivqualität des Gegners**: Tor gegen gute Defensive zählt mehr.
3. **Heim/Auswärts-Kontext**: Auswärtstor bei starkem Heimteam zählt mehr als Heimtor gegen schwaches Auswärtsteam.
4. **Aktualität**: Neuere Spiele sind wichtiger als ältere.

Aus den gewichteten Toren wird eine erwartete Torzahl `lambda` geschätzt und daraus via Poisson die Zielwahrscheinlichkeiten abgeleitet.

## Output

Pro Team und Fixture:

- `p_ge_1_goal`
- `p_ge_2_goals`
- `p_ge_3_goals`
- `lambda_weighted`
- `confidence`

Optional für UI:

- textuelle Stufe: `niedrig` | `mittel` | `hoch`
