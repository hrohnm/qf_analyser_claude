# Pattern: Goal Probability Weighted

Status: `production`

## Zweck

Für ein bevorstehendes Spiel die Wahrscheinlichkeit berechnen, dass ein Team

- mindestens 1 Tor,
- mindestens 2 Tore,
- mindestens 3 Tore

erzielt.

Dabei werden historische Tore nicht gleich gewichtet, sondern nach Kontext bewertet.

## Kernidee

Jedes historische Tor bekommt ein Gewicht basierend auf:

1. **Gegnerstärke (Elo)**: Tor gegen starkes Team zählt mehr.
2. **Defensivqualität des Gegners**: Tor gegen gute Defensive zählt mehr.
3. **Heim/Auswärts-Kontext**: Auswärtstor bei starkem Heimteam zählt mehr als Heimtor gegen schwaches Auswärtsteam.
4. **Aktualität**: Neuere Spiele sind wichtiger als ältere.

Aus den gewichteten Toren wird eine erwartete Torzahl `lambda` geschätzt und daraus via Poisson die Zielwahrscheinlichkeiten abgeleitet.

## Output

Pro Team und Fixture:

- `p_ge_1_goal`
- `p_ge_2_goals`
- `p_ge_3_goals`
- `lambda_weighted`
- `confidence`

Optional für UI:

- textuelle Stufe: `niedrig` | `mittel` | `hoch`

---

## Verbesserung v2: BTTS-Ableitung

### Motivation

BTTS (Both Teams to Score) ist einer der meistgespielten Wettmärkte. Bisher musste dieser Wert separat berechnet oder aus externen Quellen übernommen werden. Da wir für beide Teams bereits `p_ge_1_goal` berechnen, ist BTTS direkt ableitbar – mit einer kleinen Korrektur für die Abhängigkeitsstruktur.

### Formel

```
p_btts_raw = p_ge_1_goal_home × p_ge_1_goal_away
```

Das naive Produkt überschätzt BTTS leicht, weil es die positive Korrelation offensiver Partien ignoriert (wenn beide Teams offensiv spielen, treffen beide häufiger als unabhängig erwartet – aber diese Tendenz ist modellseitig bereits teilweise erfasst). Zur Sicherheit wird ein konservativer Korrelationsabschlag angewendet:

```
korrelations_abschlag = 0.95   # empirisch; Standardwert
p_btts = p_btts_raw × korrelations_abschlag
```

Der Abschlag ist bewusst moderat (5%), da die Hauptkorrelationseffekte bereits durch die kontextgewichteten λ-Werte erfasst werden.

### BTTS Nein

```
p_no_btts = 1 - p_btts
```

### Neues Output-Feld (v2)

Zusätzlich zu den bestehenden Feldern:

```json
{
  "p_ge_1_goal": 0.82,
  "p_ge_2_goals": 0.58,
  "p_ge_3_goals": 0.31,
  "lambda_weighted": 1.72,
  "confidence": "high",
  "p_btts": 0.52,
  "p_no_btts": 0.48,
  "btts_tier": "mittel"
}
```

### BTTS-Tier

| p_btts    | Tier      |
|-----------|-----------|
| < 0.40    | `niedrig` |
| 0.40–0.59 | `mittel`  |
| ≥ 0.60    | `hoch`    |

### Verwendung in nachgelagerten Pattern

`p_btts` aus diesem Pattern wird direkt in `match-result-probability` als BTTS-Basiswert verwendet, bevor dort ein eventueller Injury-Adjustment-Faktor angewendet wird.

## Datenbasis

- `fixtures` (Ergebnisse, Heim/Auswärts-Kontext)
- `team_elo_snapshot` (Gegnerstärke-Gewichtung)
- `fixture_statistics` (xG, defensive Stats optional)

## Abhängigkeiten zu anderen Pattern

- `team-elo` (für Gegnerstärke-Gewichtung der historischen Tore)
- Liefert Daten an:
  - `match-result-probability` (λ_home, λ_away, p_btts als Input)
  - `scoreline-distribution` (λ-Werte für die Ergebnismatrix)
  - `value-bet-identifier` (p_btts als Modell-Wahrscheinlichkeit für BTTS-Markt)
