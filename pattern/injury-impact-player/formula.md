# Formel / Scoring (v1)

## Überblick

`impact_score = 100 * (0.40 * importance + 0.40 * contribution + 0.20 * (1 - replaceability)) * availability_factor`

Alle Teilwerte im Bereich `0..1`.

## 1) Importance Score

- `appearance_rate_last10` = Einsätze in letzten 10 Teamspielen / 10
- `starter_proxy`:
  - Primär: Spieler erscheint in `fixture_lineups` als Starter → `1.0`
  - Fallback (keine Lineup-Daten): Spieler taucht in Events vor Minute 60 auf → `1.0`
  - Sonst (Joker / unbekannt): `0.6`
  - Achtung: Torhüter und Innenverteidiger erscheinen selten in Events — Lineup-Daten bevorzugen.

`importance = 0.7 * appearance_rate_last10 + 0.3 * starter_proxy`

## 2) Contribution Score

v1 — offensiv-lastig (vereinfacht, positionsunabhängig):

- `goal_rate = goals_last10 / max(team_goals_last10, 1)`
- `assist_rate = assists_last10 / max(team_goals_last10, 1)`
- `key_event_rate = key_events_last10 / max(team_key_events_last10, 1)` (optional)

`contribution = clamp(0.6 * goal_rate + 0.3 * assist_rate + 0.1 * key_event_rate, 0, 1)`

Bekannte Einschränkung: Torhüter, Innenverteidiger und defensive Mittelfeldspieler werden systematisch unterbewertet, da sie selten Tore/Assists erzielen. Positionsspezifische Metriken sind für v2 vorgesehen:

- GK: Save-Rate, Clean-Sheet-Anteil
- DEF: Defensive Duelle, Interceptions
- MID: Ball Recoveries, Key Passes
- FWD: aktuelle Formel anwendbar

Wenn Daten fehlen:

- Fallback auf `contribution = 0.25`
- `confidence` reduzieren

## 3) Replaceability Score

Je niedriger Ersetzbarkeit, desto höherer Impact.

Näherung (v1):

- Anzahl potenzieller Alternativen im Teamkader mit ähnlicher Rolle
- deren mittlerer Contribution-Score

`replaceability = clamp(avg_alternative_contribution * depth_factor, 0, 1)`

Fallback ohne Kaderdaten:

- `replaceability = 0.5`

## 4) Availability Factor

Verletzungstyp beeinflusst, wie sicher der Ausfall ist:

| injury_type       | availability_factor | Begründung                                      |
|-------------------|--------------------|-------------------------------------------------|
| `missing_fixture` | `1.0`              | Ausfall bestätigt                               |
| `questionable`    | `0.55`             | Historisch ~45 % der „Questionable"-Fälle spielen |

Quelle für 0.55: Näherungswert basierend auf gängigen Sport-Datenprovider-Statistiken; sollte per Backtest kalibriert werden.

## 5) Teamaggregat

Alle verletzten/fraglichen Spieler eines Teams fließen ein (kein hartes n-Limit):

`team_injury_impact = min(100, sum(impact_score für alle Spieler des Teams))`

Begründung: Ein fixes n=5 ignoriert reale Fälle mit 6–8 Verletzten und überschätzt bei nur 1–2 Verletzten nicht.

## 6) Impact Bucket

| impact_score | Code (DB)  | Anzeige (DE) |
|--------------|------------|--------------|
| `0–19`       | `low`      | Gering       |
| `20–49`      | `medium`   | Mittel       |
| `50–74`      | `high`     | Hoch         |
| `75–100`     | `critical` | Kritisch     |

DB-Enum-Wert: Englisch. Anzeige im Frontend: Deutsch (per i18n-Mapping).

## 7) Confidence

- Start bei `1.0`
- `-0.2` falls Lineup-/Minuten-Daten fehlen (Starter-Proxy auf Events angewiesen)
- `-0.2` falls Position fehlt (Contributions-Fallback aktiv)
- `-0.2` falls weniger als 5 Spiele Historie vorhanden

`confidence = clamp(value, 0.1, 1.0)`
