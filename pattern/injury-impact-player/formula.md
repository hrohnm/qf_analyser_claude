# Formel / Scoring (v1)

## Überblick

`impact_score = 100 * (0.40 * importance + 0.40 * contribution + 0.20 * (1 - replaceability)) * availability_factor`

Alle Teilwerte im Bereich `0..1`.

## 1) Importance Score

Proxy ohne vollständige Minuten-Daten (v1):

- `appearance_rate_last10` = Einsätze in letzten 10 Teamspielen / 10
- `starter_proxy` = 1.0 bei häufigen Early-Events (< 60'), sonst 0.6

`importance = 0.7 * appearance_rate_last10 + 0.3 * starter_proxy`

## 2) Contribution Score

Positionsagnostisch (v1, offensiv-lastig):

- `goal_rate = goals_last10 / team_goals_last10`
- `assist_rate = assists_last10 / team_goals_last10`
- `key_event_rate = key_events_last10 / team_key_events_last10` (optional)

`contribution = clamp(0.6 * goal_rate + 0.3 * assist_rate + 0.1 * key_event_rate, 0, 1)`

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

Verletzungstyp:

- `Missing Fixture` -> `1.0`
- `Questionable` -> `0.55`

## 5) Teamaggregat

`team_injury_impact = sum(top_n impact_score pro Team, n=5)`

Optional cap:

- `team_injury_impact = min(100, team_injury_impact)`

## 6) Confidence

Beispiel:

- Start bei `1.0`
- `-0.2` falls Minuten fehlen
- `-0.2` falls Position fehlt
- `-0.2` falls weniger als 5 Spiele Historie

`confidence = clamp(value, 0.1, 1.0)`
