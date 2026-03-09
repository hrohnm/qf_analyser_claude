# Next Steps (Implementierung)

## Phase 1: MVP Backend

1. Tabelle `fixture_goal_probability` + Migration anlegen.
2. Service `goal_probability_service.py` implementieren:
   - Input: `fixture_id`
   - Build von `lambda_weighted` je Team
   - Poisson-Werte `>=1`, `>=2`, `>=3`
3. Recompute-Job:
   - für heutige/kommende Fixtures
   - idempotent

## Phase 2: API

1. Fixture-Details erweitern:
   - `goal_probability_home`
   - `goal_probability_away`
2. Optional Endpoint:
   - `GET /api/fixtures/{fixture_id}/goal-probability`

## Phase 3: Frontend

1. Matchdetails:
   - Karte „Torwahrscheinlichkeit“
   - beide Teams: `>=1`, `>=2`, `>=3`
2. Tooltip:
   - kurze Erklärung der Gewichtung (Elo/Defensive/Heim-Auswärts)

## Phase 4: Qualität

1. Backtest:
   - Brier Score / LogLoss gegen echte Torereignisse
2. Kalibrierung:
   - `alpha` (recency), Gewichte für Elo/Def/Venue
3. Versionierung:
   - `goal_prob_v1`, `goal_prob_v2`
