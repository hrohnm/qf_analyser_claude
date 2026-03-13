# API Call Strategie – Maximale Datendichte rund um Fixtures

## Ausgangslage (Stand März 2026, Saison 2025)

| Tabelle | Einträge | Status |
|---|---|---|
| `fixtures` | 1.112 | ✅ vorhanden |
| `fixture_statistics` | 1.670 (~835 Fixtures) | ✅ vorhanden |
| `fixture_events` | 12.606 (~600 Fixtures) | ✅ vorhanden |
| `fixture_injuries` | 128 | ⚠️ nur heute |
| `fixture_odds` | 230 | ⚠️ nur heute |
| `fixture_predictions` | 20 | ⚠️ nur heute |
| `team_elo_snapshot` | 48 | ✅ vorhanden |
| `team_form_snapshot` | 144 | ✅ vorhanden |
| `fixture_lineups` | **0** | ❌ fehlt komplett |
| `fixture_player_stats` | **0** | ❌ fehlt komplett |
| `team_statistics` | **0** | ❌ fehlt komplett |
| `team_standings` | **0** | ❌ fehlt komplett |
| `player_squad` | **0** | ❌ fehlt komplett |
| `player_season_stats` | **0** | ❌ fehlt komplett |

---

## Daten-Kategorien

### Kategorie A: Per-Liga (sehr günstig, 1 Call pro Liga/Saison)

| Endpoint | Calls | Frequenz | Nutzen |
|---|---|---|---|
| `/standings?league=X&season=Y` | 2 | 1×/Tag | Tabelle, Platz, Home/Away-Bilanz, Formstring |

**Daten die wir bekommen:**
- Tabellenplatz, Punkte, Tordifferenz für alle Teams
- Home/Away getrennt: Siege/Unentschieden/Niederlagen/Tore
- Letzte 5 Ergebnisse als String (`WWDLW`)
- Qualifikationsbeschreibung (Aufstieg/Abstieg)

---

### Kategorie B: Per-Team/Saison (günstig, ~48 Calls für Championship + League One)

| Endpoint | Calls | Frequenz | Nutzen |
|---|---|---|---|
| `/teams/statistics?team=X&league=Y&season=Z` | 48 | 1×/Woche | Torminuten, Clean Sheets, Elfmeter, Formstring gesamt |
| `/players/squads?team=X` | 48 | 1×/Woche | Kader für Replaceability-Score |
| `/coachs?team=X` | 48 | 1×/Monat | Trainerdaten, Karriere |
| `/players?team=X&season=Y` | ~96-144 | 1×/Woche | Spieler-Saisonstats (paginiert, 2-3 Seiten) |

**Besonders wertvoll: `/teams/statistics` liefert:**
```
goals.for.minute:
  "0-15":  { total: 7,  percentage: "14.29%" }
  "16-30": { total: 8,  percentage: "16.33%" }
  "31-45": { total: 5,  percentage: "10.20%" }
  "46-60": { total: 6,  percentage: "12.24%" }
  "61-75": { total: 9,  percentage: "18.37%" }
  "76-90": { total: 8,  percentage: "16.33%" }
  "91-105":{ total: 6,  percentage: "12.24%" }
```
→ Basis für **Torzeit-Pattern** (wann trifft ein Team statistisch?)

**Gesamtkosten Kategorie B:** ~240-288 Calls einmalig, dann ~240/Woche

---

### Kategorie C: Per-Fixture – Aufstellungen (moderat, ~1.104 Calls pro Saison)

| Endpoint | Calls | Verfügbarkeit | Nutzen |
|---|---|---|---|
| `/fixtures/lineups?fixture=X` | 1 pro Fixture | Ab ~60min vor Ankick | Formation, Startelf, Ersatzbank |

**⚠️ Wichtige Einschränkung:**
- Lineups sind erst ~1h vor Spielbeginn verfügbar (nach offizieller Bekanntgabe)
- Historische Spiele: Lineups sind gespeichert und jederzeit abrufbar
- **Strategie:** Historisch = Fullload, Heute = kurz vor Anpfiff abrufen

**Daten:**
- Formation (z.B. `4-3-3`)
- Starting XI mit Position und Gridkoordinate
- Ersatzbank (Substitutes)
- Trikotfarben (für UI-Darstellung)

---

### Kategorie D: Per-Fixture – Spieler-Performance (teuer, ~1.104 Calls/Saison)

| Endpoint | Calls | Frequenz | Nutzen |
|---|---|---|---|
| `/fixtures/players?fixture=X` | 1 pro abgeschl. Fixture | 1× nach Spielende | Individuelle Ratings, Tore/Assists, Pässe, Dribblings |

**Daten pro Spieler:**
- `games.rating` – Note (z.B. `"7.4"`) – Basis für **Player Performance Tracker**
- `goals.total`, `goals.assists` – für injury-impact contribution ohne Näherungswert
- `passes.key` – Torschussvorlagen
- `dribbles.success` – erfolgreiche Dribblings
- `duels.won` – Zweikampfstärke
- `goals.saves` – TW-Paraden exakt

**Nutzen:** Ersetzt die aktuelle Näherung in `injury-impact-player` (Tore aus Events) durch echte Spieler-Match-Daten.

---

### Nicht nötig (intern ableitbar)

| Was | Warum kein API-Call nötig |
|---|---|
| H2H-Statistiken | Aus unserer `fixtures`-Tabelle direkt berechenbar – alle Duelle liegen vor |
| BTTS-Wahrscheinlichkeit | Aus `fixture_goal_probability` beider Teams berechnen |
| Scoreline-Distribution | Aus `goal_probability` via unabhängige Poisson |
| Over/Under-Modell | Summe beider `lambda_weighted` aus goal-probability |

---

## Priorisierte Roadmap

### 🥇 Priorität 1 – Sofort (sehr günstig, hoher Nutzen)

**~50 API Calls, 1× pro Woche**

```
1. GET /standings?league=40&season=2025       → 1 Call
2. GET /standings?league=41&season=2025       → 1 Call
3. GET /teams/statistics für alle 48 Teams    → 48 Calls
4. GET /players/squads für alle 48 Teams      → 48 Calls
```

**Neue DB-Tabellen:**
- `team_standings` (Platz, Punkte, Home/Away-Bilanz, Formstring)
- `team_season_stats` (Torminuten-Verteilung, Clean Sheets, Elfmeter, Formgesamtstring)
- `player_squad` (Kader-Tabelle für Replaceability)

**Nutzen für Pattern:**
- `injury-impact-player`: Replaceability-Score wird real (aus Kadergröße + Position)
- `team-current-form`: Standings-Formstring als Validierung
- Neues Pattern: **Torzeit-Verteilung** (wann trifft ein Team in welcher Minute?)

---

### 🥈 Priorität 2 – Nächste Woche (moderat teuer, hohes Nutzen)

**~200 API Calls einmalig**

```
5. GET /players?team=X&season=2025 für 48 Teams  → ~144 Calls
6. GET /coachs?team=X für 48 Teams               → 48 Calls
```

**Neue DB-Tabellen:**
- `player_season_stats` (Einsätze, Minuten, Tore, Assists, Rating)
- `team_coach` (Trainer + Karriere)

**Nutzen:**
- `injury-impact-player`: Contribution-Score aus echten Saisondaten statt Events-Näherung
- Neues Pattern: **Player Value Score** (Spielergewichtung basierend auf Saison-Rating)

---

### 🥉 Priorität 3 – Fullload historisch (teuer, einmalig)

**~1.100 Calls (nur für Championship + League One)**

```
7. GET /fixtures/players?fixture=X für alle ~800 abgeschl. Fixtures → ~800 Calls
```

**Neue DB-Tabelle:**
- `fixture_player_match_stats` (Rating, Tore, Assists, Pässe, Dribblings pro Spieler pro Spiel)

**Nutzen:**
- `injury-impact-player`: Echte Match-Level Daten statt Saisonschnitt
- Neues Pattern: **Player Performance Tracker** (Form eines einzelnen Spielers)

---

### ⏰ Priorität 4 – Täglich (Lineups, zeitkritisch)

**~20-30 Calls täglich (nur für heutige Fixtures)**

```
8. GET /fixtures/lineups?fixture=X für heutige Fixtures → ~20 Calls
   → Abruf: ca. 75min vor Anpfiff (nach Lineup-Bekanntgabe)
```

**Neue DB-Tabelle:**
- `fixture_lineup` (Formation, Startelf, Ersatzbank)

**Nutzen:**
- Neues Pattern: **Lineup Strength Score** (Wie stark ist die heutige Startelf vs. Saisondurchschnitt?)
- Taktische Analyse: Erkennen wenn Stammtorhüter/Stammspieler rotiert wird

---

## Neue Pattern die dadurch möglich werden

| Pattern | Benötigt | Status |
|---|---|---|
| **h2h-matchup** | DB-Fixtures (bereits vorhanden) | 📋 0 extra Calls |
| **btts-probability** | `fixture_goal_probability` | 📋 0 extra Calls |
| **scoreline-distribution** | `fixture_goal_probability` | 📋 0 extra Calls |
| **goal-timing** | `team_season_stats.goals_by_minute` | 🥇 Prio 1 |
| **lineup-strength** | `fixture_lineup` + `player_squad` | ⏰ Prio 4 |
| **player-performance-tracker** | `fixture_player_match_stats` | 🥉 Prio 3 |
| **match-result-probability (1X2)** | Elo + Form + Standings + H2H (alles intern) | 🥇 nach Prio 1 |
| **value-bet-identifier** | `fixture_odds` + alle Probability-Pattern | nach Prio 3 |

---

## Gesamt-Callverbrauch (Hochrechnung pro Saison)

| Priorität | Calls einmalig | Calls laufend | Frequenz laufend |
|---|---|---|---|
| Prio 1 (Standings + Team Stats + Squads) | ~98 | ~98 | 1×/Woche |
| Prio 2 (Player Season Stats + Coachs) | ~192 | ~192 | 1×/Woche |
| Prio 3 (Fixture Player Stats historisch) | ~800 | ~2/Tag (neue FT) | täglich |
| Prio 4 (Lineups täglich) | 0 | ~20 | täglich |
| **Gesamt einmalig** | **~1.090** | | |
| **Gesamt laufend** | | **~115/Woche** | |

Bei 7.500 Calls/Tag kein Problem – die laufenden Kosten sind minimal.

---

## Empfehlung: Was zuerst implementieren

```
Woche 1: Prio 1 + 2 → Standings, Team Stats, Squads, Player Stats
          → Sofortige Verbesserung von injury-impact + neue team_standings Tabelle

Woche 2: Prio 3 → Fixture Player Stats Fullload
          → Schaltet Player Performance Tracker frei

Täglich: Prio 4 → Lineups 75min vor Anpfiff
          → Taktische Analyse, Lineup-Strength

Parallel: Patterns h2h + btts + scoreline aus bestehenden Daten implementieren
          → 0 extra API Calls!
```
