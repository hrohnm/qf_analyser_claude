# 00 – Status / Meta

## GET /status

Kontoinfo, Subscription und API-Verbrauch.

**Parameter:** keine

**Response:**
```json
{
  "response": {
    "account": {
      "firstname": "Henning",
      "lastname": "Mueller",
      "email": "muellerhen90@icloud.com"
    },
    "subscription": {
      "plan": "Pro",
      "end": "2026-04-03T11:56:22+00:00",
      "active": true
    },
    "requests": {
      "current": 5503,
      "limit_day": 7500
    }
  }
}
```

**Felder:**
| Feld | Typ | Beschreibung |
|---|---|---|
| `account.firstname/lastname/email` | string | Kontodaten |
| `subscription.plan` | string | `Free` / `Starter` / `Pro` / `Ultra` |
| `subscription.end` | datetime | Ablaufdatum |
| `subscription.active` | bool | Ob aktiv |
| `requests.current` | int | Heute bereits verbrauchte Calls |
| `requests.limit_day` | int | Tageslimit |

**Batch:** ✗ nicht nötig

---

## GET /timezone

Alle verfügbaren Zeitzonen (als String-Array).

**Parameter:** keine

**Response:**
```json
["Africa/Abidjan", "Africa/Accra", "Europe/Berlin", "Europe/London", ...]
```
→ ~400 Einträge, nützlich für `fixtures?timezone=`

**Batch:** ✗

---

## GET /countries

Alle verfügbaren Länder.

**Parameter:**
| Param | Pflicht | Beschreibung |
|---|---|---|
| `name` | ✗ | Filtert nach Name |
| `code` | ✗ | ISO 2-Buchstaben-Code |
| `search` | ✗ | Suche (min. 2 Zeichen) |

**Response:**
```json
[
  {
    "name": "England",
    "code": "GB-ENG",
    "flag": "https://media.api-sports.io/flags/gb-eng.svg"
  }
]
```

**Batch:** ✗
