# 02 – Teams

## GET /teams

**Parameter:**
| Param | Beschreibung |
|---|---|
| `id` | Team-ID |
| `name` | Teamname |
| `league` | Liga-ID |
| `season` | Saison-Jahr |
| `country` | Ländername |
| `code` | Team-Kürzel (z.B. `MUN`) |
| `venue` | Venue-ID |
| `search` | Suche (min. 3 Zeichen) |

**Live-Beispiel:** `GET /teams?id=33`
```json
{
  "team": {
    "id": 33,
    "name": "Manchester United",
    "code": "MUN",
    "country": "England",
    "founded": 1878,
    "national": false,
    "logo": "https://media.api-sports.io/football/teams/33.png"
  },
  "venue": {
    "id": 556,
    "name": "Old Trafford",
    "address": "Sir Matt Busby Way",
    "city": "Manchester",
    "capacity": 76212,
    "surface": "grass",
    "image": "https://media.api-sports.io/football/venues/556.png"
  }
}
```

**Felder:**
| Feld | Typ | Beschreibung |
|---|---|---|
| `team.id` | int | Team-ID |
| `team.name` | string | Name |
| `team.code` | string | Kürzel |
| `team.country` | string | Land |
| `team.founded` | int | Gründungsjahr (kann null sein) |
| `team.national` | bool | Nationalmannschaft? |
| `team.logo` | string | Logo-URL |
| `venue.id` | int | Stadion-ID |
| `venue.name` | string | Stadionname |
| `venue.capacity` | int | Kapazität |
| `venue.surface` | string | `grass` / `artificial grass` |

**Batch:** ✗

---

## GET /teams/statistics

Saisonstatistiken eines Teams in einer Liga.

**Parameter (alle Pflicht):**
| Param | Beschreibung |
|---|---|
| `team` | Team-ID |
| `league` | Liga-ID |
| `season` | Saison-Jahr |
| `date` | Optional: Bis zu diesem Datum |

**Live-Beispiel:** `GET /teams/statistics?league=39&season=2025&team=33`
```json
{
  "league": { "id": 39, "name": "Premier League", "season": 2025 },
  "team": { "id": 33, "name": "Manchester United" },
  "form": "LDWLWLWWWDDLWDWDLWDDDWWWWDWWL",
  "fixtures": {
    "played": { "home": 14, "away": 15, "total": 29 },
    "wins":   { "home": 9,  "away": 5,  "total": 14 },
    "draws":  { "home": 3,  "away": 6,  "total": 9 },
    "loses":  { "home": 2,  "away": 4,  "total": 6 }
  },
  "goals": {
    "for": {
      "total": { "home": 28, "away": 21, "total": 49 },
      "average": { "home": "2.0", "away": "1.4", "total": "1.7" },
      "minute": {
        "0-15": { "total": 7, "percentage": "14.29%" },
        "16-30": { "total": 8, "percentage": "16.33%" }
      }
    },
    "against": {
      "total": { "home": 14, "away": 18, "total": 32 },
      "average": { "home": "1.0", "away": "1.2", "total": "1.1" }
    }
  },
  "biggest": {
    "streak": { "wins": 4, "draws": 2, "loses": 2 },
    "wins": { "home": "4-1", "away": "3-0" },
    "loses": { "home": "0-3", "away": "0-3" },
    "goals": {
      "for": { "home": 4, "away": 3 },
      "against": { "home": 3, "away": 3 }
    }
  },
  "clean_sheet": { "home": 5, "away": 7, "total": 12 },
  "failed_to_score": { "home": 1, "away": 4, "total": 5 },
  "penalty": {
    "scored": { "total": 4, "percentage": "80.00%" },
    "missed": { "total": 1, "percentage": "20.00%" },
    "total": 5
  },
  "lineups": [
    { "formation": "4-3-3", "played": 18 },
    { "formation": "4-2-3-1", "played": 9 }
  ],
  "cards": {
    "yellow": { "0-15": { "total": 2, "percentage": "5.71%" } },
    "red": {}
  }
}
```

**Wichtige Felder:**
| Feld | Beschreibung |
|---|---|
| `form` | Ergebnisstring (W/D/L) der gesamten Saison |
| `fixtures.*` | Gespielte/gewonnene/unentschieden/verlorene Spiele |
| `goals.for.average` | Tore pro Spiel (Heim/Auswärts/Gesamt) |
| `goals.for.minute` | Tore nach Zeitintervall (0-15', 16-30', ...) |
| `goals.against.*` | Gegentore |
| `biggest.streak.*` | Längste Siege/Unentschieden/Niederlagen-Serie |
| `clean_sheet.*` | Zu-Null-Spiele |
| `failed_to_score.*` | Spiele ohne Tor |
| `penalty.*` | Elfmeter-Statistik |
| `lineups` | Häufigste Formationen |

**Batch:** ✗ – 1 Call pro Team+Liga+Saison

---

## GET /teams/countries

Alle Länder für die Teams verfügbar sind.
Nützlich zur Filterung. Keine Parameter.

---

## GET /teams/seasons

`GET /teams/seasons?team=33` → Alle Saisons in denen Team-Daten vorhanden.
