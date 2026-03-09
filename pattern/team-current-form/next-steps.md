# Next Steps (Implementierung)

## Phase 0: Abhängigkeit

1. `team-elo` Pattern implementieren.
2. Gegnerstärke aus Elo in die Formberechnung übernehmen.
3. Ligaweiten Elo-Mittelwert je Saison berechnen (Normalisierung).

## Phase 1: MVP Backend

1. Neue Tabelle `team_form_snapshot` + Alembic-Migration.
2. Service `team_form_service.py`:
   - Berechnung für `overall`, `home`, `away`
   - Fenster `5` und `10`
   - Elo-gewichtete Result-Komponente
   - Opponent-Strength-Komponente
3. Trigger:
   - nach Fixture-Sync
   - optional nightly refresh

## Phase 2: API

1. Endpoint pro Team:
   - `GET /api/teams/{team_id}/form?season_year=2025&league_id=78`
2. Optional bulk endpoint:
   - `GET /api/leagues/{league_id}/form-table?season_year=2025&window=5`

## Phase 3: Frontend

1. Teamseite:
   - Karten für `overall/home/away` Formscore
   - Trend-Pfeil (`up/flat/down`)
2. Matchdetails:
   - kompakter Heim-vs-Auswärts Formvergleich
3. Ligaansicht:
   - Form-Badge neben Teamnamen

## Phase 4: Qualität

1. Backtest:
   - Korrelation Formscore vs. Punkte in nächsten 3 Spielen
2. Weight-Tuning (40/35/15/10) per historischen Daten
3. Versionsverwaltung:
   - `model_version` pflegen (`team_form_v1`, `v2`, ...)
