# Formel / Scoring (v1)

## Überblick

`form_score = 100 * (0.40 * elo_adjusted_result + 0.35 * performance_component + 0.15 * trend_component + 0.10 * opponent_strength_component)`

Alle Komponenten im Bereich `0..1`.

## 1) Result Component (Basis)

Punkteausbeute:

- `ppg = points_last_n / (3 * games_last_n)`
- W=3, D=1, L=0

`result_component = ppg`

## 1.1) Elo-Adjustment auf Result Component

Jedes Spiel im Fenster wird nach Gegner-Elo gewichtet:

- `opp_elo_norm = clamp(opponent_elo / league_elo_mean, 0.85, 1.15)`
- `weighted_points = raw_points * opp_elo_norm`

Dann:

- `elo_adjusted_result = sum(weighted_points) / (3 * sum(opp_elo_norm))`

Interpretation:

- Punkte gegen starke Gegner zählen mehr.
- Punkte gegen schwache Gegner zählen etwas weniger.

## 2) Performance Component (35%)

Teilmetriken über letzte `n` Spiele:

- `goal_balance = clamp((goals_for - goals_against) / max(1, games * 2), -1, 1)`
- `xg_balance = clamp((xg_for - xg_against) / max(1, games * 1.5), -1, 1)`
- `shot_quality = clamp((shots_on_target_for - shots_on_target_against) / max(1, games * 4), -1, 1)`

Auf 0..1 normalisieren:

- `norm(v) = (v + 1) / 2`

`performance_component = 0.45 * norm(goal_balance) + 0.35 * norm(xg_balance) + 0.20 * norm(shot_quality)`

## 3) Trend Component (15%)

Trend aus Vergleich der jüngsten 3 Spiele gegen die vorherigen 3:

- `recent_ppg_3`
- `previous_ppg_3`
- `delta = recent_ppg_3 - previous_ppg_3` in `[-3, 3]`

Normalisierung:

- `trend_component = clamp((delta + 3) / 6, 0, 1)`

## 4) Opponent Strength Component (10%)

Durchschnittliche Gegnerstärke im Bewertungsfenster:

- `avg_opp_elo = mean(opponent_elo_last_n)`
- `opponent_strength_component = clamp((avg_opp_elo - (league_elo_mean - 150)) / 300, 0, 1)`

Damit wird der Spielplan-Kontext direkt berücksichtigt.

## 5) Home/Away Split

Gleiche Formel, aber gefiltert:

- `scope=home`: nur Heimspiele
- `scope=away`: nur Auswärtsspiele

Für Elo:

- Home-Scope nutzt primär `opponent_elo_away`
- Away-Scope nutzt primär `opponent_elo_home`

## 6) Trend Label

Aus `delta`:

- `delta > 0.35` -> `up`
- `delta < -0.35` -> `down`
- sonst -> `flat`

## 7) Bucket Label

Aus `form_score`:

- `< 40` -> `schwach`
- `40-69.99` -> `mittel`
- `>= 70` -> `stark`
