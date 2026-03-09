# Pattern: Team Elo

Status: `draft`

## Zweck

Die Gesamtleistung eines Teams in der aktuellen Saison über eine laufend aktualisierte Stärkezahl (`elo_rating`) abbilden.

## Kernidee

Nach jedem Spiel wird die Teamstärke anhand von:

1. Ergebnis (Sieg/Unentschieden/Niederlage)
2. Torabstand
3. Heimvorteil
4. Gegnerstärke (Elo des Gegners vor dem Spiel)

angepasst.

Damit erhalten wir eine robuste saisonweite Teamqualität, die anschließend in andere Pattern einfließen kann (z. B. `team-current-form`).

## Output

- `elo_overall` pro Team (Saison)
- `elo_home` pro Team (optional Split)
- `elo_away` pro Team (optional Split)
- `elo_delta_last_5` (Trend)
- `strength_tier` (`elite` | `strong` | `average` | `weak`)

## Einsatz

- Gegnerstärke-Gewichtung in Form-Pattern
- Match-Preview: Heim-Elo vs. Auswärts-Elo
- Ranking-/Power-Table unabhängig von klassischer Tabelle
