# 03 – Players

## GET /players

Spieler-Statistiken pro Saison/Liga.

**Parameter (mindestens team+season oder id):**
| Param | Beschreibung |
|---|---|
| `id` | Spieler-ID |
| `team` | Team-ID |
| `league` | Liga-ID |
| `season` | Saison-Jahr (Pflicht mit team oder league) |
| `search` | Suche nach Name (min. 4 Zeichen) |
| `page` | Seite (Standard 1, 20 pro Seite) |

**Live-Beispiel:** `GET /players?team=33&season=2025`
```json
{
  "player": {
    "id": 526,
    "name": "A. Onana",
    "firstname": "André",
    "lastname": "Onana Onana",
    "age": 29,
    "birth": { "date": "1996-04-02", "place": "Nkol Ngok", "country": "Cameroon" },
    "nationality": "Cameroon",
    "height": "190",
    "weight": "93",
    "injured": false,
    "photo": "https://media.api-sports.io/football/players/526.png"
  },
  "statistics": [{
    "team": { "id": 33, "name": "Manchester United" },
    "league": { "id": 39, "name": "Premier League", "season": 2025 },
    "games": {
      "appearences": 15,
      "lineups": 15,
      "minutes": 1350,
      "number": null,
      "position": "Goalkeeper",
      "rating": "6.62500",
      "captain": false
    },
    "substitutes": { "in": 0, "out": 0, "bench": 2 },
    "shots": { "total": null, "on": null },
    "goals": { "total": null, "conceded": 18, "assists": null, "saves": 51 },
    "passes": { "total": null, "key": null, "accuracy": null },
    "tackles": { "total": null, "blocks": null, "interceptions": null },
    "duels": { "total": null, "won": null },
    "dribbles": { "attempts": null, "success": null, "past": null },
    "fouls": { "drawn": null, "committed": null },
    "cards": { "yellow": 0, "red": 0 },
    "penalty": { "won": null, "commited": null, "scored": 0, "missed": 0, "saved": 3 }
  }]
}
```

**Wichtige Felder:**
| Feld | Beschreibung |
|---|---|
| `player.id` | Globale Spieler-ID |
| `player.injured` | Aktuell verletzt (bool) |
| `statistics[].games.appearences` | Einsätze |
| `statistics[].games.minutes` | Spielminuten gesamt |
| `statistics[].games.rating` | Durchschnittsnote |
| `statistics[].goals.total` | Saisontore |
| `statistics[].goals.assists` | Saison-Assists |
| `statistics[].goals.saves` | Paraden (TW) |
| `statistics[].dribbles.success` | Erfolgreiche Dribblings |

**Batch:** ✗ – Paginiert (20 Spieler/Seite)

---

## GET /players/squads

Aktueller Kader eines Teams (ohne Statistiken).

**Parameter:**
| Param | Pflicht | Beschreibung |
|---|---|---|
| `team` | ✓ | Team-ID |
| `player` | ✗ | Einzelner Spieler |

**Live-Beispiel:** `GET /players/squads?team=33`
```json
{
  "team": { "id": 33, "name": "Manchester United" },
  "players": [
    { "id": 50132, "name": "A. Bayındır", "age": 27, "number": 1, "position": "Goalkeeper" },
    { "id": 162511, "name": "S. Lammens", "age": 23, "number": 31, "position": "Goalkeeper" },
    { "id": 526, "name": "A. Onana", "age": 29, "number": 24, "position": "Goalkeeper" }
  ]
}
```

**Felder:** id, name, age, number, position, photo

**Batch:** ✗

---

## GET /players/seasons

Alle Saisons in denen Spieler-Daten vorhanden.
`GET /players/seasons?player=276` → `[2010, 2011, ..., 2025]`

---

## GET /sidelined

Verletzte/gesperrte Spieler mit Dauer.

**Parameter:**
| Param | Beschreibung |
|---|---|
| `player` | Spieler-ID |
| `coach` | Trainer-ID |

**Response:** (bei player=33 → kein Eintrag aktuell)
```json
{
  "player": { "id": 276, "name": "N. Kanté" },
  "fixture": { ... },
  "type": "Knee Injury",
  "start": "2023-08-01",
  "end": "2024-02-01",
  "reason": "knee surgery"
}
```

**Batch:** ✗

---

## GET /trophies

Titel eines Spielers oder Trainers.

`GET /trophies?player=276`

```json
{
  "league": "Premier League",
  "country": "England",
  "season": "2014/2015",
  "place": "Winner"
}
```

---

## GET /transfers

Transfers eines Spielers oder Teams.

**Parameter:**
| Param | Beschreibung |
|---|---|
| `player` | Spieler-ID |
| `team` | Team-ID |

**Live-Beispiel:** `GET /transfers?team=33` (erstes Ergebnis)
```json
{
  "player": { "id": 19285, "name": "L. Steele" },
  "update": "2023-04-05T04:02:27+00:00",
  "transfers": [{
    "date": "2006-08-10",
    "type": "€ 250K",
    "teams": {
      "in":  { "id": 60, "name": "West Brom" },
      "out": { "id": 33, "name": "Manchester United" }
    }
  }]
}
```

**Felder:**
| Feld | Beschreibung |
|---|---|
| `transfers[].date` | Transferdatum |
| `transfers[].type` | Betrag (`€ 250K`, `Free`, `Loan`, `N/D`) |
| `transfers[].teams.in/out` | Aufnehmender/abgebender Verein |

**Batch:** ✗ – 271 Transfers für Man United in einem Call
