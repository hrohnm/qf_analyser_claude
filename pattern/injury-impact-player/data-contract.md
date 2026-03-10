# Data Contract

## Primärquellen (bereits vorhanden)

- `fixtures`
- `fixture_events`
- `fixture_statistics`
- `fixture_injuries`


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

## Zusätzliche Daten (optional, später)

- Spielerminuten je Match (`fixture_lineups` / Player-Stats) — bevorzugte Quelle für `starter_proxy`
- Positionsdaten pro Spieler — erforderlich für positionsspezifische Contribution (v2)
- Marktwert / ELO-artige Spielerstärke

## Ziel-Output (neue Tabellen vorgeschlagen)

### Spieler-Level: `fixture_injury_impact`

- `id`
- `fixture_id`
- `team_id`
- `player_id`
- `impact_score` (0–100)
- `impact_bucket` (`low`|`medium`|`high`|`critical`)
- `importance_score`
- `contribution_score`
- `replaceability_score`
- `availability_factor`
- `confidence` (0–1)
- `model_version` (z. B. `injury_impact_v1`)
- `computed_at`

### Team-Level-Aggregat (kann in `fixture_injury_impact` als separate Zeile oder als eigene Tabelle geführt werden)

- `fixture_id`
- `team_id`
- `team_injury_impact` (0–100, Summe aller Spieler, gecappt)
- `players_affected` (Anzahl Spieler im Aggregat)
- `computed_at`
