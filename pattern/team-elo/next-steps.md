# Next Steps (Implementierung)

## Phase 1: MVP Backend

1. Tabellen `team_elo_snapshot` (+ optional `team_elo_history`) anlegen.
2. Service `team_elo_service.py` implementieren:
   - chronologisches Elo-Update aus Fixtures
   - Output: overall/home/away
3. Batch-Recompute:
   - pro Liga + Saison
   - idempotent (vollständiger Rebuild möglich)

## Phase 2: API

1. Team-Endpunkt:
   - `GET /api/teams/{team_id}/elo?season_year=2025&league_id=78`
2. Liga-Endpunkt:
   - `GET /api/leagues/{league_id}/elo?season_year=2025`

## Phase 3: Integration in Team Form

1. `team-current-form` um Gegnergewichtung erweitern:
   - Resultat gegen hohe Elo stärker gewichten als gegen niedrige Elo
2. Optionale Formelergänzung:
   - `weighted_result = result_component * opponent_strength_factor`

## Phase 4: Qualität

1. Backtest gegen Markt-/Buchmacherindizes
2. Kalibrierung:
   - `K`, Heimvorteil, Goal-Diff-Faktor
3. Versionierung:
   - `team_elo_v1`, `team_elo_v2`
