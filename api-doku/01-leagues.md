# 01 – Leagues

## GET /leagues

**Parameter:**
| Param | Beschreibung |
|---|---|
| `id` | Liga-ID |
| `name` | Liga-Name |
| `country` | Ländername |
| `code` | ISO-Code |
| `season` | Saison-Jahr (4-stellig) |
| `team` | Team-ID |
| `type` | `league` oder `cup` |
| `current` | `true` für aktuelle Saison |
| `search` | Suche (min. 3 Zeichen) |
| `last` | Letzte N Ligen |

**Live-Beispiel:** `GET /leagues?id=39`
```json
{
  "league": {
    "id": 39,
    "name": "Premier League",
    "type": "League",
    "logo": "https://media.api-sports.io/football/leagues/39.png"
  },
  "country": {
    "name": "England",
    "code": "GB-ENG",
    "flag": "https://media.api-sports.io/flags/gb-eng.svg"
  },
  "seasons": [
    {
      "year": 2025,
      "start": "2025-08-15",
      "end": "2026-05-24",
      "current": true,
      "coverage": {
        "fixtures": {
          "events": true,
          "lineups": true,
          "statistics_fixtures": true,
          "statistics_players": true
        },
        "standings": true,
        "players": true,
        "top_scorers": true,
        "top_assists": true,
        "top_cards": true,
        "injuries": true,
        "predictions": true,
        "odds": true
      }
    }
  ]
}
```

**Felder:**
| Feld | Typ | Beschreibung |
|---|---|---|
| `league.id` | int | Liga-ID |
| `league.name` | string | Liga-Name |
| `league.type` | string | `League` / `Cup` |
| `league.logo` | string | Logo-URL |
| `country.*` | object | Land mit name/code/flag |
| `seasons[].year` | int | Saison-Jahr |
| `seasons[].start/end` | date | Start/Ende der Saison |
| `seasons[].current` | bool | Ob aktuelle Saison |
| `seasons[].coverage.*` | bool | Was für diese Saison verfügbar ist |

**Batch:** ✗ – ein Request pro Liga

---

## GET /leagues/seasons

Alle verfügbaren Saison-Jahre.

**Response:** `[2010, 2011, ..., 2025]`

**Batch:** ✗
