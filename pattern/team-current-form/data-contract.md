# Data Contract

## Primärquellen (bereits vorhanden)

- `fixtures`
- `fixture_statistics`
- `fixture_events`
- `team_elo_snapshot`

## Filtergrundlage

- nur abgeschlossene Spiele: `status_short IN (FT, AET, PEN)`
- Fenster:
  - `last_5`
  - `last_10`
- optional:
  - nur Heimspiele
  - nur Auswärtsspiele

## Benötigte Felder

Aus `fixtures`:

- `fixture_id`
- `kickoff_utc`
- `league_id`
- `season_year`
- `home_team_id`, `away_team_id`
- `home_score`, `away_score`

Aus `fixture_statistics` (Team pro Spiel):

- `expected_goals`
- `shots_total`
- `shots_on_goal`
- `ball_possession`
- `passes_total`
- `pass_accuracy`
- `fouls`
- `yellow_cards`, `red_cards`

Aus `fixture_events` (optional für Feintuning):

- Torevents
- Karten
- Späte Tore (Momentum-Indikator)

Aus `team_elo_snapshot`:

- `team_id`
- `league_id`
- `season_year`
- `elo_overall`
- `elo_home`
- `elo_away`
- `elo_delta_last_5`

## Ziel-Output (neue Tabelle vorgeschlagen)

`team_form_snapshot`

- `id`
- `team_id`
- `league_id`
- `season_year`
- `window_size` (5/10)
- `scope` (`overall`|`home`|`away`)
- `form_score`
- `result_score`
- `performance_score`
- `trend_score`
- `opponent_strength_score`
- `elo_adjusted_result_score`
- `form_trend` (`up`|`flat`|`down`)
- `form_bucket` (`schwach`|`mittel`|`stark`)
- `computed_at`
- `model_version` (z. B. `team_form_v1`)
