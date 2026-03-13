# Data Contract

## Primärquellen (bereits vorhanden)

- `fixtures`
- `fixture_events`
- `fixture_statistics`
- `fixture_injuries`

## Zusätzliche Daten (optional, später)

- Spielerminuten je Match (`fixtures/players` oder Lineups/Player-Stats)
- Positionsdaten pro Spieler
- Marktwert / ELO-artige Teamstärke

## Benötigte Felder pro Verletzungseintrag

- `fixture_id`
- `team_id`
- `player_id`
- `player_name`
- `injury_type` (Missing Fixture / Questionable)
- `injury_reason`

## Benötigte Felder für Spielerbeitrag (MVP v1)

Aus `fixture_events` über rolling window (z. B. letzte 10 Spiele):

- Tore
- Assists
- Karten (für negatives Weighting optional)
- Einsätze (abgeleitet aus Auftauchen in Events; zunächst Näherung)

Aus `fixture_statistics` auf Teamniveau:

- xG, Schüsse, Ballbesitz etc. (für Team-Context)

## Ziel-Output (neue Tabelle vorgeschlagen)

`fixture_injury_impact`

- `id`
- `fixture_id`
- `team_id`
- `player_id`
- `impact_score` (0-100)
- `importance_score`
- `contribution_score`
- `replaceability_score`
- `confidence` (0-1)
- `model_version` (z. B. `injury_impact_v1`)
- `computed_at`
