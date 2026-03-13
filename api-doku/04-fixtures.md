# 04 – Fixtures

## GET /fixtures

Hauptendpoint für Spielabruf.

**Parameter (mindestens 1 Pflicht):**
| Param | Beschreibung |
|---|---|
| `id` | Fixture-ID |
| `ids` | Mehrere IDs, Bindestrich-getrennt (max. 20): `?ids=1-2-3` ✅ BATCH |
| `live` | `all` oder kommagetrennte Liga-IDs für Live-Spiele |
| `date` | `YYYY-MM-DD` |
| `league` | Liga-ID |
| `season` | Saison-Jahr (mit `league` kombinieren) |
| `team` | Team-ID |
| `round` | Spielrunden-String (z.B. `Regular Season - 10`) |
| `status` | `NS` / `1H` / `HT` / `2H` / `ET` / `BT` / `P` / `SUSP` / `INT` / `FT` / `AET` / `PEN` / `PST` / `CANC` / `ABD` / `AWD` / `WO` |
| `venue` | Venue-ID |
| `timezone` | Zeitzone für `date`/Kickoff |
| `from` / `to` | Datumsbereich |
| `last` | Letzte N Spiele |
| `next` | Nächste N Spiele |

**⚠️ BATCH MÖGLICH:** `?ids=123-456-789` (max. 20 IDs, Bindestrich-getrennt)

**Live-Beispiel:** `GET /fixtures?league=39&season=2025&status=FT` (gekürztes Fixture-Objekt)
```json
{
  "fixture": {
    "id": 1378969,
    "referee": "Michael Oliver, England",
    "timezone": "UTC",
    "date": "2025-08-15T19:00:00+00:00",
    "timestamp": 1755284400,
    "periods": { "first": 1755284400, "second": 1755288000 },
    "venue": { "id": 550, "name": "Anfield", "city": "Liverpool" },
    "status": { "long": "Match Finished", "short": "FT", "elapsed": 90, "extra": null }
  },
  "league": {
    "id": 39, "name": "Premier League", "country": "England",
    "season": 2025, "round": "Regular Season - 1"
  },
  "teams": {
    "home": { "id": 40, "name": "Liverpool", "winner": true },
    "away": { "id": 35, "name": "Bournemouth", "winner": false }
  },
  "goals": { "home": 3, "away": 0 },
  "score": {
    "halftime": { "home": 1, "away": 0 },
    "fulltime": { "home": 3, "away": 0 },
    "extratime": { "home": null, "away": null },
    "penalty": { "home": null, "away": null }
  }
}
```

---

## GET /fixtures/rounds

Alle Spielrunden einer Liga/Saison.

**Parameter:**
| Param | Pflicht | Beschreibung |
|---|---|---|
| `league` | ✓ | Liga-ID |
| `season` | ✓ | Saison-Jahr |
| `current` | ✗ | `true` für aktuelle Runde |

**Response:** `["Regular Season - 1", "Regular Season - 2", ...]`

---

## GET /fixtures/headtohead

Direktvergleich zweier Teams.

**Parameter:**
| Param | Pflicht | Beschreibung |
|---|---|---|
| `h2h` | ✓ | `team_id_1-team_id_2` |
| `date` / `from` / `to` | ✗ | Datumsfilter |
| `league` | ✗ | Liga-Filter |
| `season` | ✗ | Saison-Filter |
| `last` / `next` | ✗ | Letzte/nächste N Spiele |
| `status` | ✗ | Spielstatus |

**Live-Beispiel:** `GET /fixtures/headtohead?h2h=33-40&season=2025`
```json
{
  "fixture": { "id": 1379043, "date": "2025-10-19T15:30:00+00:00", "status": { "short": "FT" } },
  "league": { "id": 39, "name": "Premier League", "round": "Regular Season - 9" },
  "teams": {
    "home": { "id": 40, "name": "Liverpool", "winner": true },
    "away": { "id": 33, "name": "Manchester United", "winner": false }
  },
  "goals": { "home": 3, "away": 0 },
  "score": {
    "halftime": { "home": 0, "away": 0 },
    "fulltime": { "home": 3, "away": 0 }
  }
}
```

**Batch:** ✗ (nur 1 H2H-Paar pro Call)

---

## GET /fixtures/statistics

Spielstatistiken pro Team für ein abgeschlossenes Spiel.

**Parameter:**
| Param | Pflicht | Beschreibung |
|---|---|---|
| `fixture` | ✓ | Fixture-ID |
| `team` | ✗ | Filter auf 1 Team |
| `type` | ✗ | Filter auf Statistik-Typ |

**Live-Beispiel:** `GET /fixtures/statistics?fixture=1378969`
```json
{
  "team": { "id": 40, "name": "Liverpool" },
  "statistics": [
    { "type": "Shots on Goal",     "value": 10 },
    { "type": "Shots off Goal",    "value": 7 },
    { "type": "Total Shots",       "value": 19 },
    { "type": "Blocked Shots",     "value": 2 },
    { "type": "Shots insidebox",   "value": 15 },
    { "type": "Shots outsidebox",  "value": 4 },
    { "type": "Fouls",             "value": 7 },
    { "type": "Corner Kicks",      "value": 6 },
    { "type": "Offsides",          "value": 2 },
    { "type": "Ball Possession",   "value": "61%" },
    { "type": "Yellow Cards",      "value": 1 },
    { "type": "Red Cards",         "value": null },
    { "type": "Goalkeeper Saves",  "value": 3 },
    { "type": "Total passes",      "value": 531 },
    { "type": "Passes accurate",   "value": 474 },
    { "type": "Passes %",          "value": "89%" },
    { "type": "expected_goals",    "value": "2.21" }
  ]
}
```

**Alle Statistik-Typen:**
| Typ | Einheit |
|---|---|
| Shots on Goal | int |
| Shots off Goal | int |
| Total Shots | int |
| Blocked Shots | int |
| Shots insidebox | int |
| Shots outsidebox | int |
| Fouls | int |
| Corner Kicks | int |
| Offsides | int |
| Ball Possession | % string |
| Yellow Cards | int / null |
| Red Cards | int / null |
| Goalkeeper Saves | int |
| Total passes | int |
| Passes accurate | int |
| Passes % | % string |
| expected_goals | float string |

**Batch:** ✗ – 1 Call pro Fixture

---

## GET /fixtures/events

Alle Ereignisse eines Spiels (Tore, Karten, Auswechslungen).

**Parameter:**
| Param | Pflicht | Beschreibung |
|---|---|---|
| `fixture` | ✓ | Fixture-ID |
| `team` | ✗ | Filter auf Team |
| `player` | ✗ | Filter auf Spieler |
| `type` | ✗ | `Goal` / `Card` / `subst` / `Var` |

**Live-Beispiel:** `GET /fixtures/events?fixture=1378969`
```json
{
  "time": { "elapsed": 14, "extra": null },
  "team": { "id": 35, "name": "Bournemouth" },
  "player": { "id": 18870, "name": "David Brooks" },
  "assist": { "id": null, "name": null },
  "type": "Card",
  "detail": "Yellow Card",
  "comments": "Time wasting"
}
```

**Event-Typen:**
| type | detail (Beispiele) |
|---|---|
| `Goal` | `Normal Goal`, `Own Goal`, `Penalty`, `Missed Penalty` |
| `Card` | `Yellow Card`, `Red Card`, `Yellow Red Card` |
| `subst` | `Substitution 1`, `Substitution 2`, ... |
| `Var` | `Goal Disallowed - offside`, `Penalty confirmed` |

**Batch:** ✗

---

## GET /fixtures/lineups

Aufstellungen beider Teams.

**Parameter:**
| Param | Pflicht | Beschreibung |
|---|---|---|
| `fixture` | ✓ | Fixture-ID |
| `team` | ✗ | Filter auf Team |
| `player` | ✗ | Filter auf Spieler |
| `type` | ✗ | Filter |

**Live-Beispiel:** `GET /fixtures/lineups?fixture=1378969`
```json
{
  "team": {
    "id": 40, "name": "Liverpool",
    "colors": {
      "player":     { "primary": "e41e2c", "number": "ffffff", "border": "e41e2c" },
      "goalkeeper": { "primary": "18fffb", "number": "f3f5f0", "border": "18fffb" }
    }
  },
  "coach": { "id": 2006, "name": "Arend Martijn Slot" },
  "formation": "4-2-3-1",
  "startXI": [
    { "player": { "id": 280, "name": "Alisson", "number": 1, "pos": "G", "grid": "1:1" } },
    { "player": { "id": 19220, "name": "T. Alexander-Arnold", "number": 66, "pos": "D", "grid": "2:1" } }
  ],
  "substitutes": [
    { "player": { "id": 18823, "name": "C. Kelleher", "number": 62, "pos": "G", "grid": null } }
  ]
}
```

**Felder:**
| Feld | Beschreibung |
|---|---|
| `formation` | Spielsystem z.B. `4-3-3` |
| `startXI[].player.pos` | `G` (TW), `D` (Abwehr), `M` (Mittelfeld), `F` (Angriff) |
| `startXI[].player.grid` | Position im Raster z.B. `2:1` (Reihe:Spalte) |

**Batch:** ✗

---

## GET /fixtures/players

Spieler-Statistiken pro Fixture (alle Spieler beider Teams).

**Parameter:**
| Param | Pflicht | Beschreibung |
|---|---|---|
| `fixture` | ✓ | Fixture-ID |
| `team` | ✗ | Filter auf Team |

**Live-Beispiel:** `GET /fixtures/players?fixture=1378969`
```json
{
  "team": { "id": 40, "name": "Liverpool" },
  "players": [
    {
      "player": { "id": 280, "name": "Alisson" },
      "statistics": [{
        "games": {
          "minutes": 90, "number": 1, "position": "G",
          "rating": "6.3", "captain": false, "substitute": false
        },
        "offsides": null,
        "shots": { "total": null, "on": null },
        "goals": { "total": null, "conceded": 0, "assists": null, "saves": 3 },
        "passes": { "total": 37, "key": null, "accuracy": "30" },
        "tackles": { "total": null, "blocks": null, "interceptions": null },
        "duels": { "total": null, "won": null },
        "dribbles": { "attempts": null, "success": null, "past": null },
        "fouls": { "drawn": null, "committed": null },
        "cards": { "yellow": 0, "red": 0 },
        "penalty": { "won": null, "commited": null, "scored": 0, "missed": 0, "saved": null }
      }]
    }
  ]
}
```

**Felder pro Spieler:**
| Feld | Beschreibung |
|---|---|
| `games.minutes` | Spielminuten |
| `games.rating` | Note (float als string, z.B. `"7.4"`) |
| `games.position` | `G`, `D`, `M`, `F` |
| `goals.total` | Tore |
| `goals.assists` | Assists |
| `goals.saves` | Paraden (nur TW) |
| `goals.conceded` | Gegentore (nur TW) |
| `passes.key` | Torschussvorlagen |
| `passes.accuracy` | Passquote (int) |
| `dribbles.success` | Erfolgreiche Dribblings |
| `duels.won` | Gewonnene Zweikämpfe |
| `cards.yellow/red` | Karten |

**Batch:** ✗
