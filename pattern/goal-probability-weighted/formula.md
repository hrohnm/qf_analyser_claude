# Formel / Scoring (v1)

## 1) Gewichtetet Tore aus Historie

Für jedes historische Spiel `m` des Teams:

- `g_m` = erzielte Tore des Teams in diesem Spiel
- `w_m` = Gesamtgewicht des Spiels

`weighted_goals = sum(g_m * w_m)`

`weighted_games = sum(w_m)`

`lambda_weighted = weighted_goals / max(weighted_games, eps)`

## 2) Spielgewicht `w_m`

`w_m = w_elo * w_def * w_venue * w_recency`

### 2.1 Gegner-Elo-Faktor

- `opp_elo_rel = opponent_elo / league_elo_mean`
- `w_elo = clamp(opp_elo_rel, 0.85, 1.20)`

Interpretation: Tore gegen starke Gegner erhalten höheres Gewicht.

### 2.2 Defensiv-Faktor Gegner

Defensivstärke-Index des Gegners (z. B. aus Gegentore/xGA der letzten 10 Spiele):

- `opp_def_idx` in `[0.7, 1.3]` (höher = defensiv stärker)
- `w_def = opp_def_idx`

Interpretation: Tor gegen starke Defensive zählt mehr.

### 2.3 Heim/Auswärts-Kontext

Für Torwahrscheinlichkeit des Heimteams:

- historische Heimspiele stärker gewichten (z. B. `1.10`), Auswärtsspiele `0.90`

Für Torwahrscheinlichkeit des Auswärtsteams analog umgekehrt.

### 2.4 Aktualitätsfaktor

Exponentielle Abwertung:

- `w_recency = exp(-alpha * days_since_match)` mit `alpha ~ 0.02`

Neuere Spiele zählen mehr.

## 3) Poisson-Wahrscheinlichkeiten

Mit `lambda = lambda_weighted`:

- `P(X = k) = exp(-lambda) * lambda^k / k!`
- `P(X >= 1) = 1 - P(0)`
- `P(X >= 2) = 1 - P(0) - P(1)`
- `P(X >= 3) = 1 - P(0) - P(1) - P(2)`

## 4) Korrektur mit Matchup

Optionaler Matchup-Faktor:

- `attack_team_form` aus `team_form_snapshot`
- `def_opp_form` als inverse Defensivform
- `lambda_final = lambda_weighted * matchup_factor`

`matchup_factor` typischerweise in `[0.85, 1.20]`.

## 5) Confidence

Abhängig von Datenlage:

- Anzahl gewichteter Spiele
- Anteil fehlender Stats
- Stabilität der letzten Ergebnisse

Beispiel:

- `confidence = clamp(weighted_games / 8, 0.2, 1.0)` mit Abzügen bei fehlenden Feldern.
