# Formel / Scoring (v1)

## Startwerte

- Basis-Elo pro Team zu Saisonbeginn: `1500`
- Heimvorteil: `+60 Elo` für Heimteam in der Erwartungswert-Berechnung
- Basis-`K`: `24`

## Saisonübergang

- Zu Beginn einer neuen Saison: Elo wird um 30 % zur Basis zurückgeführt.
- Formel: `elo_start = 0.70 * elo_last_season + 0.30 * 1500`
- Hintergrund: Kaderveränderungen und Trainerwechsel mindern die Aussagekraft des Vorjahreswerts.
- Für Aufsteiger / Neueinsteiger ohne Vorjahres-Elo: `elo_start = 1500`

## 1) Erwartungswert

Für Team A gegen Team B:

- `elo_a_adj = elo_a + 60` (nur wenn A Heimteam)
- `expected_a = 1 / (1 + 10^((elo_b - elo_a_adj) / 400))`
- `expected_b = 1 - expected_a`

## 2) Tatsächliches Ergebnis

- Sieg: `actual = 1.0`
- Remis: `actual = 0.5`
- Niederlage: `actual = 0.0`

## 3) Goal-Difference-Multiplikator

Kontinuierliche Formel (vermeidet harte Sprünge an Schwellenwerten):

- `gd = abs(home_score - away_score)`
- `gd_factor = 1.0` wenn `gd == 0`
- `gd_factor = 1 + 0.75 * ln(gd)` wenn `gd >= 1`

Beispielwerte:

| gd | gd_factor |
|----|-----------|
| 0  | 1.00      |
| 1  | 1.00      |
| 2  | 1.52      |
| 3  | 1.82      |
| 4  | 2.08      |
| 5  | 2.21      |

## 4) Gegnerstärke-Multiplikator

Upsets (Sieg gegen stärkeren Gegner) werden stärker belohnt:

- `strength_factor = clamp(opponent_elo / own_elo, 0.85, 1.15)`

## 5) Elo-Update

- `delta = K * gd_factor * strength_factor * (actual - expected)`
- `elo_new = elo_old + delta`

Analog mit invertierten Rollen fürs Gegnerteam.

## 6) Split-Werte

- `elo_overall`: Update nach jedem Match (primäres Signal)
- `elo_home`: nur Updates aus Heimspielen
- `elo_away`: nur Updates aus Auswärtsspielen

Alle drei starten zu Saisonbeginn beim selben `elo_start`-Wert.

## 7) Trend: elo_delta_last_5

Ableitung aus `team_elo_history` (scope = `overall`):

- `elo_delta_last_5 = elo_after[game_n] - elo_before[game_{n-4}]`
- Entspricht dem Gesamt-Elo-Gewinn/-Verlust über die letzten 5 Partien.
- Wenn weniger als 5 Spiele vorhanden: `null`

## 8) Tier-Einteilung

Symmetrisch um die Basislinie 1500 (±100 pro Tier):

| Elo-Bereich | Code (DB) | Anzeige (DE)  |
|-------------|-----------|---------------|
| `>= 1600`   | `elite`   | Spitzenklasse |
| `1500–1599` | `strong`  | Stark         |
| `1400–1499` | `average` | Durchschnitt  |
| `< 1400`    | `weak`    | Schwach       |

DB-Enum-Wert: Englisch. Anzeige im Frontend: Deutsch (per i18n-Mapping).
