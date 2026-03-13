# Pattern: Home Advantage Calibration

Status: `draft`

## Zweck

Kalibrierung des team-spezifischen Heimvorteils als eigenständigen Faktor, der über den allgemeinen Liga-Heimvorteil hinausgeht. Manche Teams spielen zuhause deutlich besser als auswärts (ausgeprägte Heimstärke), andere kaum. Dieser team-spezifische Faktor fließt in `match-result-probability` und `goal-probability-weighted` ein.

## Kernidee

Der Standard-Elo-Heimvorteil ist ein konstanter Bonus für alle Teams (typisch: +50 Elo-Punkte). Tatsächlich ist der Heimvorteil jedoch team-spezifisch: Einige Teams profitieren massiv von ihrer Heimkulisse, anderen ist der Spielort fast egal. Dieses Pattern berechnet für jedes Team einen kalibrierten `home_factor`, der den realen Heim/Auswärts-Split widerspiegelt.

### Berechnung des Home Factor

```
# Basis: Ergebnis-Split Heim vs. Auswärts (normiert)
ppg_home = punkte_gesamt_heim / spiele_heim       # Punkte pro Spiel Heim
ppg_away = punkte_gesamt_auswärts / spiele_auswärts  # Punkte pro Spiel Auswärts

liga_avg_ppg_home = ∅ ppg_home aller Teams der Liga
liga_avg_ppg_away = ∅ ppg_away aller Teams der Liga
liga_avg_home_factor = liga_avg_ppg_home / liga_avg_ppg_away

# Team-spezifischer Faktor (relativ zum Liga-Durchschnitt)
team_raw_factor = ppg_home / ppg_away
home_factor = team_raw_factor / liga_avg_home_factor

# home_factor = 1.0 → genau durchschnittlicher Heimvorteil
# home_factor > 1.0 → stärkerer Heimvorteil als Liga-Schnitt
# home_factor < 1.0 → schwächerer Heimvorteil (fast gleiche Leistung heim/auswärts)
```

### Tor-basierte Ergänzung

Neben Punkten wird auch die Tor-Dominanz als Signal einbezogen:

```
goal_diff_home = (tore_heim - gegentore_heim) / spiele_heim
goal_diff_away = (tore_auswärts - gegentore_auswärts) / spiele_auswärts

goal_home_factor = goal_diff_home / goal_diff_away  (wenn beide positiv)
```

### Elo-Bereinigung

Der rohe Heim/Auswärts-Split wird für Gegnerstärke bereinigt. Ein Team, das zuhause nur schwache Gegner hatte und auswärts immer gegen Spitzenteams spielte, würde sonst einen verzerrten Home Factor erhalten:

```
bereinigter_ppg_home = ppg_home - elo_korrekturfaktor_heim
bereinigter_ppg_away = ppg_away - elo_korrekturfaktor_auswärts
```

### Mindestdaten-Anforderung

- Mindestens 5 Heimspiele und 5 Auswärtsspiele für verlässliche Schätzung
- Bei weniger Spielen: Shrinkage Richtung Liga-Durchschnitt (1.0)

```
gewicht_realdaten = min(spiele_heim, spiele_auswärts) / 10  # max 1.0
home_factor_final = home_factor × gewicht_realdaten + 1.0 × (1 - gewicht_realdaten)
```

### Klassifikation

| home_factor Wert | Tier            | Beschreibung                              |
|------------------|-----------------|-------------------------------------------|
| ≥ 1.30           | `fortress`      | Ausgeprägter Heimvorteil (Festung)        |
| 1.10 – 1.29      | `home_strong`   | Überdurchschnittlicher Heimvorteil        |
| 0.90 – 1.09      | `neutral`       | Durchschnittlicher/kein Heimvorteil       |
| < 0.90           | `road_team`     | Kaum Unterschied heim/auswärts            |

## Output-Felder

Pro Team und Saison:

```json
{
  "team_id": 42,
  "season": 2025,
  "league_id": 78,
  "spiele_heim": 13,
  "spiele_auswärts": 13,
  "ppg_home": 2.15,
  "ppg_away": 1.31,
  "ppg_home_bereinigt": 2.08,
  "ppg_away_bereinigt": 1.35,
  "liga_avg_home_factor": 1.28,
  "home_factor_raw": 1.54,
  "home_factor_final": 1.20,
  "home_factor_tier": "home_strong",
  "goals_home_avg": 2.1,
  "goals_away_avg": 1.4,
  "conceded_home_avg": 0.9,
  "conceded_away_avg": 1.6,
  "confidence_weight": 1.0,
  "computed_at": "2026-03-10T12:00:00Z"
}
```

### Verwendung in anderen Pattern

Der `home_factor_final` wird in `goal-probability-weighted` als Multiplikator auf λ_home angewendet:

```
λ_home_adjusted = λ_home_basis × (home_factor_final / liga_avg_home_factor)
```

In `match-result-probability` fließt er als 5%-Gewicht ein.

## Datenbasis

- `fixtures` + Ergebnisse (heim/auswärts Tore, Punkte)
- `team_elo_snapshot` (für Gegnerstärke-Bereinigung)
- `/teams/statistics` (API-Football, Heim/Auswärts-Split der Saisonstatistik)
- Tabelle: `team_home_advantage` (team_id, season, league_id, home_factor, tier, computed_at)

## Abhängigkeiten zu anderen Pattern

- `team-elo` (für Gegnerstärke-Bereinigung, optional)
- Liefert Daten an:
  - `goal-probability-weighted` (λ-Anpassung)
  - `match-result-probability` (5%-Gewicht im Aggregationsmodell)
  - `ai-match-picks` (Kontext: "Team X ist eine echte Heimfestung")

## Nutzen für Wettscheine/Analyse

- **Heimsieg-Märkte**: `fortress`-Teams verdienen einen höheren 1X2-Heimsieg-Preis als ihr Elo alleine vermuten lässt
- **Asian Handicap**: Home Factor hilft bei der Kalibrierung des fairen Handicap-Wertes
- **Travel-Fähigkeit**: `road_team`-Teams verlieren wenig bei Auswärtsspielen – wichtig gegen die Erwartung eines standard Heimvorteils
- **Saisonübergreifend**: Manche Teams kultivieren ihren Heimvorteil über Jahre (Ultras, Stadionatmosphäre, Rasenplatz) – dieses Muster ist persistent und wird hier erfasst
