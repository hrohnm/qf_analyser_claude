# Data Contract

## Primärquellen (bereits vorhanden)

- `fixtures`
- `fixture_statistics`
- `team_elo_snapshot`
- optional: `team_form_snapshot`

## Benötigte Eingaben pro historisches Match

Aus `fixtures`:

- `fixture_id`
- `kickoff_utc`
- `league_id`
- `season_year`
- `home_team_id`, `away_team_id`
- `home_score`, `away_score`
- `status_short` (nur FT/AET/PEN)

Aus `team_elo_snapshot`:

- `team_id`
- `elo_overall`
- `elo_home`
- `elo_away`

Aus `fixture_statistics` (Defensive Kontexte):

- `expected_goals` (xG against Proxy)
- `shots_on_goal` (allowed)
- `goals_against` (aus fixtures ableitbar)

## Ziel-Output (neue Tabelle vorgeschlagen)

`fixture_goal_probability`

- `id`
- `fixture_id`
- `team_id`
- `is_home`
- `season_year`
- `league_id`
- `lambda_weighted`
- `p_ge_1_goal`
- `p_ge_2_goals`
- `p_ge_3_goals`
- `confidence`
- `sample_size`
- `computed_at`
- `model_version` (z. B. `goal_prob_v1`)
