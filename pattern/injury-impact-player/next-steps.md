# Next Steps (Implementierung)

## Phase 1: MVP Backend

1. Neue Tabelle `fixture_injury_impact` + Alembic-Migration anlegen.
2. Service `injury_impact_service.py` implementieren:
   - Inputs: `fixture_id`, `season_year`, `league_id`
   - Berechnung gemäß `formula.md`
3. In bestehenden Daily-Job integrieren:
   - Nach Injuries-Sync Impact berechnen
   - Nur für heutige Fixtures / kommende Fixtures

## Phase 2: API

1. Fixture-Details Endpoint erweitern:
   - `injury_impacts: []`
   - `team_injury_impact_home`
   - `team_injury_impact_away`

## Phase 3: Frontend

1. Match-Details:
   - In Injury-Spalten zusätzlich Badge pro Spieler (Impact)
   - Team-Header mit Summen-Impact
2. Tooltip für Transparenz:
   - Warum hoher Impact (z. B. hoher Toranteil, geringe Ersetzbarkeit)

## Phase 4: Qualität

1. Backtesting gegen historische Spiele:
   - Korrelation zwischen Team-Impact und Abweichung vom Erwartungswert
2. Gewichte kalibrieren (0.40/0.40/0.20)
3. Versionierung:
   - `model_version` pflegen und Vergleich v1/v2 ermöglichen
