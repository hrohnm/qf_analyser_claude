# 07 – Predictions

## GET /predictions

KI-Vorhersage der API für ein Fixture.

**Parameter:**
| Param | Pflicht | Beschreibung |
|---|---|---|
| `fixture` | ✓ | Fixture-ID |

**Live-Beispiel:** `GET /predictions?fixture=1378969`
```json
{
  "predictions": {
    "winner": {
      "id": 40,
      "name": "Liverpool",
      "comment": "Win or draw"
    },
    "win_or_draw": true,
    "under_over": null,
    "goals": {
      "home": null,
      "away": null
    },
    "advice": "Double chance : Liverpool or draw",
    "percent": {
      "home": "50%",
      "draw": "50%",
      "away": "0%"
    }
  },
  "league": {
    "id": 39, "name": "Premier League",
    "country": "England", "season": 2025
  },
  "teams": {
    "home": {
      "id": 40, "name": "Liverpool",
      "last_5": {
        "form": "WWWWW",
        "att": "88%",
        "def": "69%",
        "goals": {
          "for":     { "total": 14, "average": "2.8" },
          "against": { "total": 5,  "average": "1.0" }
        }
      },
      "league": {
        "form": "WWWWWWWWWWWWWWWWWWWWWWWWWLWWWWWWWWWWWWWWWWWWWW",
        "fixtures": {
          "played":  { "home": 1, "away": 0, "total": 1 },
          "wins":    { "home": 1, "away": 0, "total": 1 },
          "draws":   { "home": 0, "away": 0, "total": 0 },
          "loses":   { "home": 0, "away": 0, "total": 0 }
        },
        "goals": {
          "for":     { "total": { "home": 3, "away": 0, "total": 3 }, "average": { "home": "3.0", "away": "0.0", "total": "3.0" } },
          "against": { "total": { "home": 0, "away": 0, "total": 0 }, "average": { "home": "0.0", "away": "0.0", "total": "0.0" } }
        },
        "biggest": {
          "streak":      { "wins": 1, "draws": 0, "loses": 0 },
          "wins":        { "home": "3-0", "away": null },
          "loses":       { "home": null,  "away": null },
          "goals":       { "for": { "home": 3, "away": 0 }, "against": { "home": 0, "away": 0 } }
        },
        "clean_sheet": { "home": 1, "away": 0, "total": 1 },
        "failed_to_score": { "home": 0, "away": 0, "total": 0 },
        "penalty": {
          "scored": { "total": 0, "percentage": "0%" },
          "missed": { "total": 0, "percentage": "0%" },
          "total": 0
        }
      }
    },
    "away": { "...": "analog home" }
  },
  "comparison": {
    "form":    { "home": "43%", "away": "57%" },
    "att":     { "home": "43%", "away": "57%" },
    "def":     { "home": "55%", "away": "45%" },
    "poisson_distribution": { "home": "31%", "away": "69%" },
    "h2h":     { "home": "55%", "away": "45%" },
    "goals":   { "home": "43%", "away": "57%" },
    "total":   { "home": "45%", "away": "55%" }
  }
}
```

**Alle Felder:**

### predictions
| Feld | Typ | Beschreibung |
|---|---|---|
| `winner.id/name` | int/string | Vorhergesagter Gewinner (null bei keinem klaren Favoriten) |
| `winner.comment` | string | Kommentar z.B. `"Win or draw"` |
| `win_or_draw` | bool | Doppelte Chance empfohlen? |
| `under_over` | string/null | z.B. `"+2.5"` oder `"-2.5"` oder null |
| `goals.home/away` | string/null | Erwartete Tore (z.B. `"1.5"`) |
| `advice` | string | Empfehlung im Klartext |
| `percent.home/draw/away` | string | Wahrscheinlichkeiten in % |

### teams.X.last_5
| Feld | Beschreibung |
|---|---|
| `form` | Letzte 5 Ergebnisse (W/D/L) |
| `att` | Angriffsstärke letzte 5 (%) |
| `def` | Defensivstärke letzte 5 (%) |
| `goals.for.total/average` | Tore in letzten 5 |
| `goals.against.total/average` | Gegentore in letzten 5 |

### teams.X.league
Vollständige Saisonstatistiken pro Team identisch zu `/teams/statistics`:
- `form`, `fixtures`, `goals`, `biggest`, `clean_sheet`, `failed_to_score`, `penalty`

### comparison
| Feld | Beschreibung |
|---|---|
| `form` | Formvergleich (home% vs away%) |
| `att` | Angriffsvergleich |
| `def` | Defensivvergleich |
| `poisson_distribution` | Poisson-Wahrscheinlichkeiten |
| `h2h` | Head-to-Head Vergleich |
| `goals` | Tor-Vergleich |
| `total` | Gesamtbewertung |

**Nutzung im Spinnendiagramm:** Die 6 `comparison`-Werte (form, att, def, poisson, h2h, goals) sind die Achsen.

**Batch:** ✗ – 1 Call pro Fixture
