# 10 – Transfers

## GET /transfers

Transfer-Historie eines Spielers oder Teams.

**Parameter:**
| Param | Beschreibung |
|---|---|
| `player` | Spieler-ID |
| `team` | Team-ID |

**Live-Beispiel:** `GET /transfers?team=33` (gekürztes Ergebnis, 271 Transfers total)
```json
{
  "player": { "id": 19285, "name": "L. Steele" },
  "update": "2023-04-05T04:02:27+00:00",
  "transfers": [
    {
      "date": "2006-08-10",
      "type": "€ 250K",
      "teams": {
        "in":  { "id": 60,  "name": "West Brom",         "logo": "..." },
        "out": { "id": 33,  "name": "Manchester United",  "logo": "..." }
      }
    }
  ]
}
```

**Transfer-Typen (type-Feld):**
| type | Bedeutung |
|---|---|
| `€ 500K` / `£ 85M` etc. | Ablöse in Währung + Betrag |
| `Free` | Ablösefrei |
| `Loan` | Leihe |
| `End of Loan` | Leihe beendet (Rückkehr) |
| `N/D` | Nicht bekannt |

**Felder:**
| Feld | Beschreibung |
|---|---|
| `player.id/name` | Spieler |
| `update` | Letztes Update-Datum |
| `transfers[].date` | Transferdatum |
| `transfers[].type` | Ablöse/Art |
| `transfers[].teams.in` | Aufnehmender Verein |
| `transfers[].teams.out` | Abgebender Verein |

**Batch:** ✗ – aber 1 Call gibt alle Transfers eines Teams
