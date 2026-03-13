# 08 – Coachs (Trainer)

## GET /coachs

**Parameter:**
| Param | Beschreibung |
|---|---|
| `id` | Trainer-ID |
| `team` | Team-ID (aktueller Trainer) |
| `search` | Suche nach Name (min. 3 Zeichen) |

**Live-Beispiel:** `GET /coachs?team=33`
```json
{
  "id": 2898,
  "name": "R. Amorim",
  "firstname": "Rúben",
  "lastname": "Amorim",
  "age": 40,
  "birth": {
    "date": "1985-01-27",
    "place": "Lisbon",
    "country": "Portugal"
  },
  "nationality": "Portugal",
  "height": null,
  "weight": null,
  "photo": "https://media.api-sports.io/football/coachs/2898.png",
  "team": {
    "id": 33,
    "name": "Manchester United",
    "logo": "https://media.api-sports.io/football/teams/33.png"
  },
  "career": [
    {
      "team": { "id": 33, "name": "Manchester United" },
      "start": "2024-11-01",
      "end": null
    },
    {
      "team": { "id": 573, "name": "Sporting CP" },
      "start": "2020-03-05",
      "end": "2024-11-04"
    }
  ]
}
```

**Felder:**
| Feld | Beschreibung |
|---|---|
| `id` | Trainer-ID |
| `name` | Name |
| `age` | Alter |
| `nationality` | Nationalität |
| `height/weight` | Körperdaten (oft null) |
| `team` | Aktuelles Team |
| `career[].start/end` | Beschäftigungszeitraum (end=null wenn aktuell) |

**Hinweis:** Pro Team-Anfrage kommen aktuelle UND frühere Trainer zurück (3 bei Man United: Amorim, ten Hag, Solskjaer...).

**Batch:** ✗
