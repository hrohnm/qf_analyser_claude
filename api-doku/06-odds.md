# 06 – Odds

## GET /odds

Pre-Match Quoten für ein Fixture.

**Parameter:**
| Param | Beschreibung |
|---|---|
| `fixture` | Fixture-ID (Pflicht für spezifische Quoten) |
| `league` | Liga-ID |
| `season` | Saison-Jahr |
| `date` | `YYYY-MM-DD` |
| `timezone` | Zeitzone |
| `page` | Seite (20 Fixtures/Seite) |
| `bookmaker` | Bookmaker-ID filtern (z.B. `32` = Betano) |
| `bet` | Bet-Typ-ID filtern (z.B. `1` = Match Winner) |

**⚠️ BATCH-TEST:** `GET /odds?fixtures=1378969-1378970`
→ **Fehler:** `{"fixtures": "The Fixtures field do not exist."}`
→ **KEIN BATCH möglich!** 1 Call pro Fixture.

**Live-Beispiel:** `GET /odds?fixture=1378969&bookmaker=32`
(Fixture aus vergangener Saison → keine Quoten mehr verfügbar)

**Typische Response-Struktur:**
```json
{
  "fixture": { "id": 12345, "timezone": "UTC", "date": "2026-03-10T...", "timestamp": 1741564800 },
  "league": { "id": 40, "name": "Championship", "country": "England", "season": 2025 },
  "update": "2026-03-10T10:00:00+00:00",
  "bookmakers": [
    {
      "id": 32,
      "name": "Betano",
      "bets": [
        {
          "id": 1,
          "name": "Match Winner",
          "values": [
            { "value": "Home", "odd": "1.85" },
            { "value": "Draw", "odd": "3.40" },
            { "value": "Away", "odd": "4.20" }
          ]
        },
        {
          "id": 5,
          "name": "Goals Over/Under",
          "values": [
            { "value": "Over 2.5", "odd": "1.90" },
            { "value": "Under 2.5", "odd": "1.85" },
            { "value": "Over 1.5", "odd": "1.22" },
            { "value": "Under 1.5", "odd": "4.50" },
            { "value": "Over 0.5", "odd": "1.06" }
          ]
        },
        {
          "id": 12,
          "name": "Double Chance",
          "values": [
            { "value": "Home/Draw", "odd": "1.18" },
            { "value": "Home/Away", "odd": "1.25" },
            { "value": "Draw/Away", "odd": "2.10" }
          ]
        },
        {
          "id": 16,
          "name": "Total - Home",
          "values": [
            { "value": "Over 0.5", "odd": "1.28" },
            { "value": "Under 0.5", "odd": "3.50" },
            { "value": "Over 1.5", "odd": "2.10" },
            { "value": "Under 1.5", "odd": "1.67" }
          ]
        },
        {
          "id": 17,
          "name": "Total - Away",
          "values": [
            { "value": "Over 0.5", "odd": "1.35" },
            { "value": "Under 0.5", "odd": "3.00" },
            { "value": "Over 1.5", "odd": "2.40" }
          ]
        }
      ]
    }
  ]
}
```

**⚠️ Wichtige Beobachtung – Wertereihenfolge:**
Betano sortiert die Werte NICHT nach Linie aufsteigend. `Over 1.5` kann vor `Over 0.5` erscheinen.
→ **Immer den value-String prüfen, nie auf Index verlassen!**

## Alle genutzten Bet-IDs (Betano, bet_id 32)

| bet_id | Name | Werte-Beispiele |
|---|---|---|
| 1 | Match Winner | Home, Draw, Away |
| 5 | Goals Over/Under | Over/Under 0.5, 1.5, 2.5, 3.5, 4.5 |
| 6 | Goals O/U First Half | Over/Under 0.5, 1.5 |
| 12 | Double Chance | Home/Draw, Home/Away, Draw/Away |
| 16 | Total - Home | Over/Under 0.5, 1.5, 2.5 |
| 17 | Total - Away | Over/Under 0.5, 1.5, 2.5 |
| 26 | Both Teams Score | Yes, No |
| 105 | Home Team Score First Half | Yes, No |
| 106 | Away Team Score First Half | Yes, No |
| 218 | Home Win to Nil | Yes, No |
| 219 | Away Win to Nil | Yes, No |
| 231 | Exact Score | 1-0, 2-0, 2-1, 0-0, ... |
| 232 | Double Chance First Half | Home/Draw, Home/Away, Draw/Away |

---

## GET /odds/live

Live-Quoten für laufende Spiele.

**Parameter:**
| Param | Beschreibung |
|---|---|
| `fixture` | Fixture-ID |
| `league` | Liga-ID |
| `bet` | Bet-Typ-ID |

**Struktur identisch zu /odds**, zusätzlich `main: true/false` pro Bet.

---

## GET /odds/mapping

Alle verfügbaren Bet-Typen der API (332 insgesamt).

**Parameter:** keine

**Beispiel:**
```json
{ "id": 1, "name": "Match Winner" },
{ "id": 2, "name": "Home/Away" },
{ "id": 3, "name": "Asian Handicap" },
{ "id": 4, "name": "Exact Score" },
{ "id": 5, "name": "Goals Over/Under" }
```

Vollständige Liste: 332 Bet-Typen verfügbar.

---

## GET /odds/bookmakers

Alle verfügbaren Bookmaker (31 insgesamt).

**Wichtige Bookmaker:**
| ID | Name |
|---|---|
| 1 | 10Bet |
| 6 | Bwin |
| 8 | Bet365 |
| 16 | William Hill |
| 32 | **Betano** ← unser Standard |

---

## GET /odds/bets

Alle Bet-Typen (332 Einträge). Identisch zu `/odds/mapping`.
