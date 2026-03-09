# Pattern: Injury Impact Player

Status: `draft`

## Zweck

Den erwarteten negativen Einfluss eines fehlenden oder fraglichen Spielers auf sein Team quantifizieren.

## Kernidee

Der Impact eines Spielers hängt von drei Bausteinen ab:

1. **Bedeutung im Team** (Einsatzzeit, Startelf-Quote, Rollenrelevanz)
2. **Leistungsbeitrag** (Tore, Assists, xG/xA, defensive Aktionen je Position)
3. **Ersetzbarkeit** (Qualität möglicher Ersatzspieler und Tiefe des Kaders)

Diese Bausteine werden zu einem normierten `impact_score` (0-100) kombiniert.

## Output

- `impact_score` pro Spieler und Fixture
- `impact_bucket`:
  - `0-19` gering
  - `20-49` mittel
  - `50-74` hoch
  - `75-100` kritisch
- Teamaggregat:
  - `team_injury_impact_home`
  - `team_injury_impact_away`

## Einsatz auf der Match-Detailseite

- Pro Team eine Liste der fehlenden/fraglichen Spieler
- Neben jedem Spieler ein Badge mit Impact-Bucket
- Oberhalb der Liste ein Team-Gesamtscore
