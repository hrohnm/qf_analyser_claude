# Pattern: H2H Matchup

Status: `draft`

## Zweck

Systematische Auswertung der historischen Direktduelle (Head-to-Head) zweier Teams auf Basis bereits gespeicherter Fixture-Daten – ohne einen einzigen zusätzlichen API-Call. Das Pattern liefert einen H2H-Score (0–100 aus Heimperspektive) sowie statistische Tendenz-Werte, die in `match-result-probability` und `match-comparison` einfließen.

## Kernidee

In der lokalen Datenbank sind bereits alle synchronisierten Fixtures gespeichert. Zwei Teams, die sich häufig begegnen (z. B. in derselben Liga über mehrere Saisons), haben also bereits eine verwertbare Direktduel-Geschichte. Dieses Pattern durchsucht die `fixtures`-Tabelle nach allen Spielen, bei denen Heim- oder Auswärtsteam der aktuelle Matchup-Partner sind, und berechnet daraus:

1. **Ergebnistendenz**: Wer gewinnt die Direktduelle häufiger?
2. **Tormuster**: Wie torreich sind diese Duelle historisch?
3. **Heimvorteil-Validierung**: Bestätigt die H2H-Historie den allgemeinen Heimvorteil?
4. **Aktualitätsgewichtung**: Neuere Duelle zählen mehr als ältere (exponentieller Decay)

### Scoring-Formel

Für jedes H2H-Fixture wird ein gewichtetes Ergebnis aus Heimperspektive (aktueller Heimmannschaft) berechnet:

```
ergebnis_punkte = 3 (Sieg) | 1 (Unentschieden) | 0 (Niederlage)
alter_in_tagen  = (heute - fixture_datum).days
aktualitaets_gewicht = exp(-alter_in_tagen / 365)

gewichtete_punkte = ergebnis_punkte × aktualitaets_gewicht
```

Der finale H2H-Score normiert die Summe auf 0–100:

```
max_moeglich = Σ(3 × aktualitaets_gewicht) über alle N Fixtures
h2h_score_home = (Σ gewichtete_punkte_home / max_moeglich) × 100
h2h_score_away = 100 - h2h_score_home
```

### Mindestanforderung

- Mindestens 3 gemeinsame Fixtures in der DB → sonst `confidence: low`, neutrale Werte (50/50)
- Empfohlen: mindestens 5 Fixtures für `confidence: medium`, 10+ für `confidence: high`

### Tor-Analyse

Über alle H2H-Fixtures:

```
h2h_avg_goals_home = Σ(tore_heimteam_in_h2h_spielen) / N
h2h_avg_goals_away = Σ(tore_auswärtsteam_in_h2h_spielen) / N
h2h_avg_total      = h2h_avg_goals_home + h2h_avg_goals_away
h2h_btts_rate      = Anzahl Spiele mit ≥1 Tor beider Teams / N
h2h_over_2_5_rate  = Anzahl Spiele mit >2,5 Toren gesamt / N
```

## Output-Felder

Pro Fixture-Paarung (Heim/Auswärts-neutral gespeichert, Heimperspektive angepasst):

```json
{
  "fixture_id": 12345,
  "team_home_id": 42,
  "team_away_id": 77,
  "h2h_fixtures_count": 12,
  "h2h_score_home": 58.3,
  "h2h_score_away": 41.7,
  "h2h_home_wins": 6,
  "h2h_draws": 3,
  "h2h_away_wins": 3,
  "h2h_avg_goals_home": 1.8,
  "h2h_avg_goals_away": 1.2,
  "h2h_avg_total_goals": 3.0,
  "h2h_btts_rate": 0.58,
  "h2h_over_2_5_rate": 0.67,
  "h2h_last_fixture_result": "home_win",
  "h2h_last_fixture_date": "2025-11-15",
  "confidence": "high",
  "computed_at": "2026-03-10T12:00:00Z"
}
```

## Datenbasis

Ausschließlich lokale Daten – kein API-Call nötig:

- `fixtures` (Ergebnisse, Datum, Heim-/Auswärtsteam-ID)
- `fixture_scores` oder Score-Felder innerhalb `fixtures`

Optional zur Anreicherung (falls bereits geladen):
- `fixture_statistics` (xG, Possession) für qualitative H2H-Analyse

## Abhängigkeiten zu anderen Pattern

- Keine Abhängigkeit zu anderen Pattern (eigenständig berechenbar)
- Liefert Daten an:
  - `match-result-probability` (10% Gewicht im Aggregations-Modell)
  - `match-comparison` (H2H-Dimension im Spinnendiagramm)
  - `ai-match-picks` (historischer Kontext für Claude)

## Nutzen für Wettscheine/Analyse

- **1X2**: H2H-Score stärkt oder schwächt die Elo/Form-basierte Einschätzung
- **BTTS**: h2h_btts_rate ist ein direktes historisches Signal
- **Over/Under**: h2h_over_2_5_rate gibt historische Tendenz ohne Modell-Annahmen
- **Psychologischer Faktor**: Teams mit starker H2H-Dominanz performen oft besser als das reine Elo erwarten lässt
- **Null Extrakosten**: Da ausschließlich lokale Daten verwendet werden, entstehen keine API-Kosten
