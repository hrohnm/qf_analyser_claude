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

---

## Verbesserung v2: Positionsgewichtung

### Problem in v1

Der `replaceability_score` fiel auf einen pauschal 0.5-Fallback zurück, sobald keine Kaderdaten verfügbar waren. Außerdem wurden alle Positionen gleich gewichtet – ein fehlender Flügelspieler wurde genauso bewertet wie ein fehlender Torhüter oder zentraler Innenverteidiger.

### Positionsgewichte (neu)

Jeder Spieler erhält einen `position_weight_base`, der die strukturelle Wichtigkeit seiner Position im Team widerspiegelt:

| Position             | Kürzel | position_weight_base | Begründung                                      |
|----------------------|--------|----------------------|-------------------------------------------------|
| Torwart              | GK     | 1.00                 | Kein echtes Äquivalent, jede Schwäche direkt messbar |
| Innenverteidiger     | CB     | 0.85                 | Taktische Stabilität, Zweikampf-Basis           |
| Defensives Mittelfeld| DM     | 0.80                 | Schaltzentrale, Pressing-Anker                  |
| Rechts-/Linksverteidiger | RB/LB | 0.70             | Wichtig, aber oft austauschbar durch Umstellungen |
| Zentrales Mittelfeld | CM     | 0.75                 | Ballverteilung, Laufwege                        |
| Offensives Mittelfeld| AM     | 0.70                 | Kreativität, aber oft durch Systemwechsel ersetzbar |
| Mittelfeld (allg.)   | MF     | 0.72                 | Durchschnitt aus CM/DM/AM                       |
| Flügel               | LW/RW  | 0.60                 | Offensiv wichtig, aber taktisch variabel        |
| Stürmer / Mittelstürmer | ST/CF | 0.75              | Tore, Pressing – Ersatz vorhanden, aber Qualitätsabfall |
| Unbekannt            | –      | 0.60                 | Konservativer Fallback                          |

### Replaceability aus echten Kaderdaten (neu)

Anstatt eines Pauschal-Fallbacks wird der `replaceability_score` aus den tatsächlichen Squad-Daten berechnet:

```python
def compute_replaceability(injured_player, squad, player_season_stats):
    """
    Berechnet, wie gut ein Spieler durch Kader-Alternativen ersetzt werden kann.
    Returns: replaceability_score (0.0 = kein Ersatz, 1.0 = vollständig ersetzbar)
    """
    position = injured_player.position
    injured_rating = player_season_stats[injured_player.id].avg_rating  # z.B. 7.2

    # Kandidaten: Spieler gleicher Position im Kader (außer verletzter Spieler selbst)
    candidates = [
        p for p in squad
        if p.position == position and p.id != injured_player.id
    ]

    if not candidates:
        return 0.1  # Keine direkte Alternative → stark geschwächt

    # Bestes Rating unter den Alternativen
    best_candidate_rating = max(
        player_season_stats.get(c.id, {}).get("avg_rating", 5.5)
        for c in candidates
    )

    # Replaceability = Verhältnis beste Alternative / verletzter Spieler
    # Gedeckelt auf [0.1, 1.0]
    raw = best_candidate_rating / injured_rating if injured_rating > 0 else 0.5
    return max(0.1, min(1.0, raw))
```

### Aktualisierte Gesamt-Formel

```
usage_score       = (starts / spiele_gesamt) × 0.6 + (minuten / (spiele × 90)) × 0.4
performance_score = normiert aus Toren, Assists, Rating, defensiven Aktionen (positionsabhängig)
replaceability    = compute_replaceability(verletzer_spieler, kader, saisonstatistiken)

raw_impact = (usage_score × 0.35)
           + (performance_score × 0.40)
           + (position_weight_base × 0.25)

impact_score = raw_impact × (1 - replaceability) × 100
```

### Positionsspezifische Performance-Gewichte (neu)

Die `performance_score`-Berechnung berücksichtigt nun positionsspezifische Metriken:

| Position | Primär-Metriken (70%)                     | Sekundär-Metriken (30%)         |
|----------|-------------------------------------------|---------------------------------|
| GK       | Goals conceded/game, saves_pct            | Pässe, Libero-Aktionen          |
| CB/DM    | Tackles, Interceptions, Duelle gewonnen   | Pässe, Ballgewinne              |
| CM/AM    | Key Passes, xA, Assists                   | Tacklings, Ballgewinne          |
| LW/RW/ST | Goals, xG, Assists, Dribblings erfolgreich | Key Passes, Schüsse             |

## Datenbasis

- `fixture_injuries` (Verletzungsstatus pro Fixture)
- `player_season_stats` (Einsätze, Minuten, Tore, Assists, Rating)
- `squad` (Kaderliste mit Positionen)
- `fixtures` (Gesamt-Spielanzahl für Normierung)

## Abhängigkeiten zu anderen Pattern

- Keine direkten Pattern-Abhängigkeiten (liest aus API-Daten)
- Liefert Daten an:
  - `match-result-probability` (5%-Gewicht als λ-Reduktionsfaktor)
  - `ai-match-picks` (Verletzungsliste als Claude-Kontext)
