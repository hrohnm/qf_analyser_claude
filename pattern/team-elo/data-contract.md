# Data Contract

## Primärquellen (bereits vorhanden)

- `fixtures`
- optional für spätere Verfeinerung: `fixture_statistics`

## Pflichtfelder aus `fixtures`

- `id`
- `season_year`
- `league_id`
- `kickoff_utc`
- `home_team_id`, `away_team_id`
- `home_score`, `away_score`
- `status_short` (nur abgeschlossene Matches)

## Verarbeitung

- Nur abgeschlossene Spiele (`FT`, `AET`, `PEN`)
- Chronologische Verarbeitung nach `kickoff_utc`
- Elo-Update pro Match für beide Teams

## Ziel-Output (neue Tabelle vorgeschlagen)

`team_elo_snapshot`

- `id`
- `team_id`
- `league_id`
- `season_year`
- `elo_overall`
- `elo_home`
- `elo_away`
- `games_played`
- `games_home`
- `games_away`
- `elo_delta_last_5`
- `strength_tier`
- `computed_at`
- `model_version` (z. B. `team_elo_v1`)

Optional Historie:

`team_elo_history`

- `id`
- `team_id`
- `fixture_id`
- `league_id`
- `season_year`
- `scope` (`overall` | `home` | `away`)
- `elo_before` (elo_overall vor diesem Match)
- `elo_after` (elo_overall nach diesem Match)
- `elo_change`
- `computed_at`
