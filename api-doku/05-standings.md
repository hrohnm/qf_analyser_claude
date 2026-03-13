# 05 – Standings

## GET /standings

Ligatabelle für eine Saison.

**Parameter:**
| Param | Pflicht | Beschreibung |
|---|---|---|
| `league` | ✓ (oder team) | Liga-ID |
| `season` | ✓ | Saison-Jahr |
| `team` | ✗ | Nur Tabellenposition eines Teams |

**Live-Beispiel:** `GET /standings?league=39&season=2025`
```json
{
  "league": {
    "id": 39,
    "name": "Premier League",
    "country": "England",
    "season": 2025,
    "standings": [[
      {
        "rank": 1,
        "team": { "id": 42, "name": "Arsenal", "logo": "..." },
        "points": 67,
        "goalsDiff": 37,
        "group": "Premier League",
        "form": "WWWDD",
        "status": "same",
        "description": "Promotion - Champions League (League phase)",
        "all": {
          "played": 29, "win": 21, "draw": 4, "lose": 4,
          "goals": { "for": 68, "against": 31 }
        },
        "home": {
          "played": 14, "win": 11, "draw": 2, "lose": 1,
          "goals": { "for": 36, "against": 13 }
        },
        "away": {
          "played": 15, "win": 10, "draw": 2, "lose": 3,
          "goals": { "for": 32, "against": 18 }
        },
        "update": "2026-03-10T00:00:00+00:00"
      }
    ]]
  }
}
```

**Felder:**
| Feld | Beschreibung |
|---|---|
| `rank` | Tabellenplatz |
| `points` | Punkte |
| `goalsDiff` | Tordifferenz |
| `form` | Letzte 5 Ergebnisse (W/D/L) |
| `status` | `up` / `down` / `same` (Trendpfeil) |
| `description` | Qualifikation/Abstieg Beschreibung |
| `all/home/away.played/win/draw/lose` | Spielbilanz gesamt/Heim/Auswärts |
| `all/home/away.goals.for/against` | Tore gesamt/Heim/Auswärts |

**Batch:** ✗ – aber 1 Call gibt Gesamttabelle (alle Teams)

**Hinweis:** `standings` ist ein Array von Arrays – das äußere Array entspricht Gruppen (bei Ligen immer 1 Gruppe).
