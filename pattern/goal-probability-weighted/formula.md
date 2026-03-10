# Formel / Scoring (v1)

## 1) Gewichtetet Tore aus Historie

Für jedes historische Spiel `m` des Teams:

- `g_m` = erzielte Tore des Teams in diesem Spiel
- `w_m` = Gesamtgewicht des Spiels

`weighted_goals = sum(g_m * w_m)`

`weighted_games = sum(w_m)`

`lambda_weighted = weighted_goals / max(weighted_games, eps)`

## 2) Spielgewicht `w_m`

Additive Kombination der Kontextfaktoren, multipliziert mit Aktualität:

`w_m = (1 + (w_elo - 1) + (w_def - 1) + (w_venue - 1)) * w_recency`

Vereinfacht: `w_m = (w_elo + w_def + w_venue - 2) * w_recency`

Dadurch addieren sich die Einflüsse statt sich multiplikativ zu potenzieren (kein Extremwert-Compounding).

### 2.1 Gegner-Elo-Faktor

- `opp_elo_rel = opponent_elo / league_elo_mean`
- `w_elo = clamp(opp_elo_rel, 0.90, 1.15)`

Symmetrisches Clamp: max. ±15 % Abweichung.
Interpretation: Tore gegen starke Gegner erhalten höheres Gewicht.

### 2.2 Defensiv-Faktor Gegner

Defensivstärke-Index aus den letzten 10 Spielen des Gegners:

```
goals_conceded_per_game = opp_goals_conceded_last10 / max(opp_games_last10, 1)
xga_per_game            = opp_xga_last10 / max(opp_games_last10, 1)

goal_ratio = league_avg_goals_conceded / max(goals_conceded_per_game, 0.1)
xga_ratio  = league_avg_xga / max(xga_per_game, 0.1)

opp_def_idx = clamp(0.6 * goal_ratio + 0.4 * xga_ratio, 0.85, 1.15)
```

`w_def = opp_def_idx`

Interpretation: `opp_def_idx > 1` → Gegner lässt weniger Tore als Liga-Durchschnitt → Tor zählt mehr.

### 2.3 Heim/Auswärts-Kontext

Für Torwahrscheinlichkeit des **Heimteams**:
- historische Heimspiele: `w_venue = 1.10`
- historische Auswärtsspiele: `w_venue = 0.90`

Für Torwahrscheinlichkeit des **Auswärtsteams**: Gewichte umgekehrt.

### 2.4 Aktualitätsfaktor

Exponentielle Abwertung:

- `w_recency = exp(-alpha * days_since_match)` mit `alpha = 0.02`

Neuere Spiele zählen mehr. Beispiel: 30 Tage → `w_recency ≈ 0.55`

## 3) Poisson-Wahrscheinlichkeiten

Edge Case: Falls `lambda_weighted == 0` (Team hat im gesamten Fenster kein Tor erzielt), wird `lambda_weighted = 0.1` als Minimum gesetzt, um nicht-triviale Ausgaben zu gewährleisten.

Mit `lambda = lambda_weighted`:

- `P(X = k) = exp(-lambda) * lambda^k / k!`
- `P(X >= 1) = 1 - P(0)`
- `P(X >= 2) = 1 - P(0) - P(1)`
- `P(X >= 3) = 1 - P(0) - P(1) - P(2)`

## 4) Korrektur mit Matchup

Optionaler Matchup-Faktor basierend auf aktueller Form beider Teams:

```
attack_form_norm = clamp(attack_team_form_score / 50, 0.70, 1.50)
def_form_norm    = clamp(def_opp_form_score / 50,    0.70, 1.50)

matchup_factor = clamp(attack_form_norm / def_form_norm, 0.85, 1.20)
```

- `attack_team_form_score`: `form_score` des angreifenden Teams aus `team_form_snapshot`
- `def_opp_form_score`: `form_score` des Gegners (Defensivkontext)
- Bei `form_score = 50` (Durchschnitt) beider Teams: `matchup_factor = 1.0` (keine Korrektur)

`lambda_final = lambda_weighted * matchup_factor`

## 5) Confidence

Abhängig von Datenlage:

- Anzahl gewichteter Spiele
- Anteil fehlender Stats
- Stabilität der letzten Ergebnisse

Beispiel:

- `confidence = clamp(weighted_games / 8, 0.2, 1.0)` mit Abzügen bei fehlenden Feldern.
