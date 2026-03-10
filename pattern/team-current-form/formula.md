# Formel / Scoring (v1)

## Überblick

`form_score = 100 * (0.40 * elo_adjusted_result + 0.40 * performance_component + 0.20 * trend_component)`

Alle Komponenten im Bereich `0..1`.

Hinweis: Eine separate `opponent_strength_component` entfällt, da die Gegnerstärke bereits vollständig im `elo_adjusted_result` (Abschnitt 1.1) berücksichtigt wird.

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

## 2) Performance Component (40%)

Teilmetriken über letzte `n` Spiele:

- `goal_balance = clamp((goals_for - goals_against) / max(1, games * 2), -1, 1)`
- `xg_balance = clamp((xg_for - xg_against) / max(1, games * 1.5), -1, 1)`
- `shot_quality = clamp((shots_on_target_for - shots_on_target_against) / max(1, games * 4), -1, 1)`

Auf 0..1 normalisieren:

- `norm(v) = (v + 1) / 2`

`performance_component = 0.45 * norm(goal_balance) + 0.35 * norm(xg_balance) + 0.20 * norm(shot_quality)`

## 3) Trend Component (20%)

Trend aus Vergleich der jüngsten 3 Spiele gegen die vorherigen 3:

- `recent_ppg_3`
- `previous_ppg_3`
- `delta = recent_ppg_3 - previous_ppg_3` in `[-3, 3]`

Normalisierung:

- `trend_component = clamp((delta + 3) / 6, 0, 1)`

## 4) Cold-Start-Handling

Wenn weniger Spiele vorhanden sind als das gewählte Fenster (`last_5` / `last_10`):

- Berechnung erfolgt mit den tatsächlich verfügbaren Spielen.
- `games_used` wird im Output festgehalten.
- Bei `games_used < 3`: `confidence` wird auf maximal `0.5` begrenzt; `form_score_home` / `form_score_away` werden als `null` ausgegeben (zu wenig Split-Daten).
- Saisongrenze: Spiele aus der Vorsaison werden nicht in das Fenster einbezogen.

## 5) Home/Away Split

Gleiche Formel, aber gefiltert:

- `scope=home`: nur Heimspiele
- `scope=away`: nur Auswärtsspiele

Für Elo:

- Home-Scope nutzt primär `opponent_elo_away`
- Away-Scope nutzt primär `opponent_elo_home`

## 6) Home/Away Confidence

Split-Scores haben eine eigene Konfidenz, da sie auf weniger Spielen basieren:

- `confidence_split = clamp(games_used_split / 5, 0.2, 1.0)`
- Bei `games_used_split < 3`: Score wird als `null` ausgegeben.

## 7) Trend Label

Aus `delta` (PPG-Differenz in `[-3, 3]`):

| delta          | Code (DB) | Anzeige (DE) |
|----------------|-----------|--------------|
| `> 0.35`       | `up`      | Aufwärts     |
| `< -0.35`      | `down`    | Abwärts      |
| sonst          | `flat`    | Stabil       |

## 8) Bucket Label

Aus `form_score`:

| form_score    | Code (DB) | Anzeige (DE) |
|---------------|-----------|--------------|
| `< 40`        | `weak`    | Schwach      |
| `40–69.99`    | `medium`  | Mittel       |
| `>= 70`       | `strong`  | Stark        |

DB-Enum-Wert: Englisch. Anzeige im Frontend: Deutsch (per i18n-Mapping).
