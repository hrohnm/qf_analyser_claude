# 09 – Injuries

## GET /injuries

Verletzungs- und Sperrliste für ein Fixture oder eine Liga.

**Parameter:**
| Param | Beschreibung |
|---|---|
| `fixture` | Fixture-ID |
| `ids` | ✅ **BATCH: Mehrere Fixture-IDs, Bindestrich-getrennt (max. 20):** `?ids=1-2-3` |
| `league` | Liga-ID |
| `season` | Saison-Jahr (mit league) |
| `team` | Team-ID |
| `player` | Spieler-ID |
| `date` | `YYYY-MM-DD` |
| `timezone` | Zeitzone |

**⚠️ BATCH MÖGLICH:** `GET /injuries?ids=1378969-1378970-1378971`
→ Gibt Verletzungsdaten für alle angegebenen Fixtures zurück (max. 20 IDs pro Call).
→ **Spart bis zu 95% der Calls vs. Einzel-Requests!**

**Live-Beispiel:** `GET /injuries?fixture=1378969`
```json
{
  "player": {
    "id": 1125,
    "name": "Ryan Christie",
    "photo": "https://media.api-sports.io/football/players/1125.png",
    "type": "Missing Fixture",
    "reason": "fitness"
  },
  "team": {
    "id": 35,
    "name": "Bournemouth",
    "logo": "https://media.api-sports.io/football/teams/35.png"
  },
  "fixture": {
    "id": 1378969,
    "timezone": "UTC",
    "date": "2025-08-15T19:00:00+00:00",
    "timestamp": 1755284400
  },
  "league": {
    "id": 39,
    "season": 2025,
    "name": "Premier League"
  }
}
```

**Felder:**
| Feld | Typ | Beschreibung |
|---|---|---|
| `player.id` | int | Spieler-ID |
| `player.name` | string | Spielername |
| `player.type` | string | `"Missing Fixture"` oder `"Questionable"` |
| `player.reason` | string | Verletzungsgrund: `"fitness"`, `"illness"`, `"knee"`, `"muscle"`, etc. |
| `team.id/name` | int/string | Welches Team betroffen |
| `fixture.id/date` | int/datetime | Betroffenes Fixture |
| `league.id/season` | int | Liga und Saison |

**Injury Types:**
| type | Bedeutung |
|---|---|
| `Missing Fixture` | Spieler sicher nicht dabei |
| `Questionable` | Einsatz fraglich (ca. 55% Chance ausgefallen) |

**Nutzung in unserem Projekt:**
```
GET /injuries?ids=FIX1-FIX2-...-FIX20  (20 Fixtures pro Call)
```
→ 1.104 Fixtures / 20 = ~56 Calls für die gesamte Championship + League One Saison
