# Pattern: Team Elo

Status: `production`

## Zweck

Die Gesamtleistung eines Teams in der aktuellen Saison über eine laufend aktualisierte Stärkezahl (`elo_rating`) abbilden.

## Kernidee

Nach jedem Spiel wird die Teamstärke anhand von:

1. Ergebnis (Sieg/Unentschieden/Niederlage)
2. Torabstand
3. Heimvorteil
4. Gegnerstärke (Elo des Gegners vor dem Spiel)

angepasst.

Damit erhalten wir eine robuste saisonweite Teamqualität, die anschließend in andere Pattern einfließen kann (z. B. `team-current-form`).

## Output

- `elo_overall` pro Team (Saison)
- `elo_home` pro Team (optional Split)
- `elo_away` pro Team (optional Split)
- `elo_delta_last_5` (Trend)
- `strength_tier` (`elite` | `strong` | `average` | `weak`)

## Einsatz

- Gegnerstärke-Gewichtung in Form-Pattern
- Match-Preview: Heim-Elo vs. Auswärts-Elo
- Ranking-/Power-Table unabhängig von klassischer Tabelle

---

## Verbesserung v2: Cross-Season-Kontinuität

### Problem in v1

Zu Saisonbeginn startet jedes Team auf dem Startwert 1500 zurück. Das bedeutet: Ein Champions-League-Finalist und ein Aufsteiger beginnen mit identischem Elo. Die ersten 5–8 Spieltage der neuen Saison liefern dadurch extrem rauschende Elo-Werte – die Vergangenheitsstärke wird vollständig ignoriert.

### Lösung: Saisonübergang mit Carry-Over

Anstatt auf 1500 zurückzusetzen, wird der Elo-Wert der Vorsaison zu einem definierten Anteil in die neue Saison übernommen und dann in Richtung des Saison-Starts-Mittelpunkts (1500) gedämpft:

```
elo_saison_start_neu = elo_saison_ende_alt × carry_over_faktor
                     + 1500 × (1 - carry_over_faktor)

carry_over_faktor = 0.70  # 70% Persistenz, 30% Regression zur Mitte
```

**Beispiel:**
- Bayern beendet die Saison mit Elo 1820
- Saison-Startwert neu: `1820 × 0.70 + 1500 × 0.30 = 1274 + 450 = 1724`
- Aufsteiger ohne Vorsaison-Daten: Startet bei 1500 (Liga-Durchschnitt) oder optional bei 1450 (leichter Malus für Neulinge)

### Datenmigration

Für Teams ohne Vorsaison-Eintrag in der DB (Aufsteiger, Neuzugänge in einer Liga):

```
elo_start = 1500 - liga_tier_malus

# liga_tier_malus:
#   Bundesliga (top): 0
#   2. Bundesliga:   -30
#   3. Liga:         -60
#   Aufsteiger aus Unterklasse: -100 (startet auf 1400)
```

### K-Faktor-Anpassung

In den ersten 10 Spielen einer neuen Saison wird der K-Faktor erhöht, damit das Elo schneller auf die tatsächliche Saisonform konvergiert:

```
K = 40  für Spieltage 1–10 (hohes Update)
K = 25  für Spieltage 11–20
K = 20  für Spieltage 21+ (Standardwert)

# Zusätzlich: Torabstand-Multiplikator (wie bisher)
K_adjusted = K × goal_diff_multiplier
```

### Technische Umsetzung

```python
def get_season_start_elo(team_id, new_season, db):
    prev_season = new_season - 1
    prev_snapshot = db.query(TeamEloSnapshot).filter_by(
        team_id=team_id, season=prev_season
    ).order_by(desc("computed_at")).first()

    if prev_snapshot:
        carry_over = 0.70
        return prev_snapshot.elo_overall * carry_over + 1500 * (1 - carry_over)
    else:
        # Aufsteiger/Neueinsteiger: Liga-Tier-Malus
        league_malus = get_league_tier_malus(team_id, new_season, db)
        return 1500 - league_malus
```

### Neue Output-Felder (v2)

Zusätzlich zu den bestehenden Feldern:

- `elo_season_start` – Startwert zu Saisonbeginn (nach Carry-Over)
- `elo_carry_over_from_prev_season` – Vorsaison-Elo, der als Basis diente
- `carry_over_applied` – Boolean, ob Carry-Over verfügbar war

## Datenbasis

- `fixtures` (Ergebnisse für Elo-Updates)
- `team_elo_snapshot` (fortlaufende Snapshots pro Spieltag)
- Neue Spalten: `elo_season_start`, `elo_carry_over_from_prev_season`

## Abhängigkeiten zu anderen Pattern

- Liefert Daten an alle anderen Pattern (zentrale Stärke-Metrik)
- Benötigt: `fixtures` mit Ergebnissen und Datum
