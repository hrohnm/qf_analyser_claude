# Pattern: Team Current Form

Status: `production`

## Zweck

Die aktuelle Leistungsform eines Teams quantifizieren, um kurzfristige Trends (stark/schwach) vor einem Match sichtbar zu machen.

## Kernidee

Der Form-Score soll nicht nur Ergebnisse (W/D/L), sondern auch Leistungsqualität enthalten:

1. **Resultatform**: Punkteausbeute in den letzten Spielen
2. **Performanceform**: Tore, xG, Schussqualität, Defensivstabilität
3. **Kontextform**: Heim/Auswärts-Split und Gegnerstärke (über Team-Elo)

Das Ergebnis ist ein `form_score` (0-100) plus Trend-Richtung.

## Output

- `form_score_overall` (0-100)
- `form_score_home` (0-100)
- `form_score_away` (0-100)
- `form_trend`: `up` | `flat` | `down`
- `form_bucket`: `schwach` | `mittel` | `stark`

## Einsatz im Frontend

- Teamseite: großes Form-Modul mit Verlauf der letzten 5/10 Spiele
- Matchdetails: kompakter Heim-vs-Auswärts Formvergleich
- optional Badge in Liga-Tabelle (z. B. letzte 5 Spiele)
