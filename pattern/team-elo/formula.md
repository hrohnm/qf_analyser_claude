# Formel / Scoring (v1)

## Startwerte

- Basis-Elo pro Team zu Saisonbeginn: `1500`
- Heimvorteil: `+60 Elo` für Heimteam in Erwartungswert-Berechnung
- Basis-`K`: `24`

## 1) Erwartungswert

Für Team A gegen Team B:

- `expected_a = 1 / (1 + 10^((elo_b - elo_a_adj)/400))`
- `elo_a_adj = elo_a + home_advantage` (nur wenn A Heimteam)

## 2) Tatsächliches Ergebnis

- Sieg: `actual = 1.0`
- Remis: `actual = 0.5`
- Niederlage: `actual = 0.0`

## 3) Goal-Difference-Multiplikator

- `gd = abs(goal_diff)`
- `gd_factor`:
  - `1` bei `gd = 1`
  - `1.5` bei `gd = 2`
  - `1.75` bei `gd = 3`
  - `2.0` bei `gd >= 4`

## 4) Gegnerstärke-Multiplikator (optional v1.1)

Für Upsets stärker belohnen:

- `strength_factor = clamp((opponent_elo / own_elo), 0.85, 1.15)`

## 5) Elo-Update

- `delta = K * gd_factor * (actual - expected)`
- `elo_new = elo_old + delta`

Analog mit invertierten Rollen fürs Gegnerteam.

## 6) Split-Werte

- `elo_overall`: Update nach jedem Match
- `elo_home`: nur Updates aus Heimspielen
- `elo_away`: nur Updates aus Auswärtsspielen

## 7) Tier-Einteilung

- `>= 1650`: `elite`
- `1550-1649`: `strong`
- `1450-1549`: `average`
- `< 1450`: `weak`
