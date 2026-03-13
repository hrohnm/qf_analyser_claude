# Pattern Library

Dieses Verzeichnis sammelt wiederverwendbare Analyse-Pattern.

## Ziel

- Pro fachlicher Fragestellung ein eigener Unterordner
- Klare Trennung zwischen Konzept, Datenbedarf und Implementierungsplan
- Nachvollziehbare Weiterentwicklung ohne Ad-hoc-Logik

## Struktur pro Pattern

Jedes Pattern bekommt einen Ordner:

`pattern/<pattern-name>/`

Empfohlene Dateien:

- `README.md` – fachliches Ziel, Annahmen, Ergebnis
- `data-contract.md` – benötigte Datenfelder/Tabellen/APIs
- `formula.md` – Berechnungslogik und Scoring
- `next-steps.md` – konkrete Implementierungsschritte

## Namenskonvention

- Kleinschreibung
- Wörter mit Bindestrich
- Beispiel: `injury-impact-player`

## Reifegrad

Optional pro Pattern kennzeichnen:

- `draft` – erste Idee
- `validated` – fachlich geprüft
- `production` – implementiert und aktiv genutzt

## Pattern-Übersicht

### Produktive Pattern (production)

| Pattern                      | Zweck                                              | Output (Kern)                          |
|------------------------------|----------------------------------------------------|----------------------------------------|
| `team-elo`                   | Saisonweite Teamstärke via Elo-Rating              | elo_overall, strength_tier             |
| `team-current-form`          | Kurzfristige Formverfassung (letzte 5–10 Spiele)   | form_score 0-100, form_trend           |
| `goal-probability-weighted`  | Torwahrscheinlichkeit via gewichteter Poisson      | p_ge_1/2/3_goal, lambda, p_btts (v2)  |
| `ai-match-picks`             | Claude-generierte Wett-Empfehlungen pro Fixture    | 5 strukturierte Picks + Top Scorer     |

### Draft-Pattern (konzeptionell fertig, Implementierung ausstehend)

| Pattern                        | Zweck                                                       | Output (Kern)                                     |
|--------------------------------|-------------------------------------------------------------|---------------------------------------------------|
| `injury-impact-player`         | Impact fehlender Spieler (v2: Positionsgewichtung)          | impact_score 0-100, team_injury_impact            |
| `match-comparison`             | Eigene 7-dimensionale Vergleichsmatrix (Spinnendiagramm)    | form/att/def/poisson/h2h/goals/total (home/away)  |
| `match-result-probability`     | Aggregierte finale 1X2/BTTS/O/U Wahrscheinlichkeiten        | p_home_win, p_draw, p_away_win, p_btts, p_over_X  |
| `h2h-matchup`                  | Head-to-Head Analyse aus lokalen Fixture-Daten (0 API-Calls)| h2h_score, h2h_btts_rate, h2h_over_2_5_rate       |
| `scoreline-distribution`       | Vollständige Ergebnismatrix via Poisson                     | P(i,j) für alle Scorelines, top_scorelines        |
| `value-bet-identifier`         | Modell-Probs vs. Buchmacher → Edge + EV                     | edge, ev, value_tier, kelly_fraction              |
| `goal-timing`                  | Torminuten-Verteilung pro Team (wann trifft/kassiert?)      | angriffs_index/defensiv_index pro 15-Min-Fenster  |
| `home-advantage-calibration`   | Team-spezifischer Heimvorteil-Faktor                        | home_factor, home_factor_tier (fortress/neutral)  |

## Abhängigkeits-Graph

```
team-elo ──────────────────┬──────────────────────────────────────────────┐
                           │                                              │
team-current-form ─────────┤                                              │
                           ▼                                              │
goal-probability-weighted ─┬──► scoreline-distribution                   │
                           │         │                                    │
home-advantage-calibration ┤         ▼                                    │
                           │    match-result-probability ◄───────────────┤
h2h-matchup ───────────────┤         │                                    │
                           │         ▼                                    │
injury-impact-player ──────┘    value-bet-identifier                      │
                                     │                                    │
goal-timing ────────────────────────►│                                    │
                                     ▼                                    │
                                ai-match-picks ◄──────────────────────────┘
```

## Verbesserungen v2 (geplant)

| Pattern                     | Verbesserung                                                              |
|-----------------------------|---------------------------------------------------------------------------|
| `team-elo`                  | Cross-Season-Kontinuität: 70% Carry-Over aus Vorsaison statt Reset auf 1500 |
| `injury-impact-player`      | Positionsgewichtung (TW/IV > OM > Flügel), Replaceability aus echten Kaderdaten |
| `goal-probability-weighted` | BTTS direkt ableiten: p_btts = p_ge_1_home × p_ge_1_away × Korrelationsabschlag |
