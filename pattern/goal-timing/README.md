# Pattern: Goal Timing

Status: `draft`

## Zweck

Analyse der zeitlichen Torverteilung eines Teams über den Spielverlauf hinweg – basierend auf den Minuten-segmentierten Torstatistiken aus `/teams/statistics`. Das Pattern beantwortet: In welchen Spielphasen trifft ein Team typischerweise, und in welchen Phasen kassiert es Gegentore?

## Kernidee

Die `fixture_events`-Tabelle (bereits vorhanden) enthält für jedes Tor die exakte Spielminute (`elapsed`). Daraus lassen sich team-spezifische Timing-Profile ableiten – **ohne extra API-Calls** und mit höherer Granularität als die 15-Minuten-Fenster aus `/teams/statistics`:

1. **Angriffsprofil**: In welchen Minuten ist ein Team gefährlich?
2. **Defensivprofil**: Wann ist ein Team verwundbar?
3. **Halbzeit-Split**: Ist ein Team ein Starten/Finisher oder bricht es ein?
4. **Frühe-/Späte-Tore**: Relevanz für spezifische Wettmärkte (1. Tor, letztes Tor, HT-Score)

### Normierung der Zeitfenster

Da die Zeitfenster unterschiedlich lang sind (15 Minuten), werden die Toranzahlen auf eine einheitliche Rate pro 15 Minuten normiert. Nachspielzeiten (45+, 90+) werden anteilig dem jeweiligen Halbzeit-Fenster zugerechnet.

### Timing-Score pro Fenster

```
tore_rate[fenster]  = tore_im_fenster / spiele_gesamt
gegentore_rate[fenster] = gegentore_im_fenster / spiele_gesamt

angriffs_index[fenster] = tore_rate[fenster] / ∅_tore_rate_alle_fenster
defensiv_index[fenster] = 1 - (gegentore_rate[fenster] / ∅_gegentore_rate_alle_fenster)
```

Ein `angriffs_index` > 1.0 bedeutet überdurchschnittliche Torgefahr in diesem Fenster.

### First/Last Goal Wahrscheinlichkeit

Aus dem Profil lässt sich die Wahrscheinlichkeit schätzen, dass ein Team das erste Tor (in den ersten 30 Minuten) oder das letzte Tor (nach Minute 75) erzielt:

```
p_first_goal_scorer  = tore_0_30 / (tore_0_30_heim + tore_0_30_gast)
p_comeback_potential = tore_61_90 / (tore_gesamt × normierung)
```

### Halbzeit-Profil

```
ht_attack_ratio  = tore_1_halbzeit / (tore_1_halbzeit + tore_2_halbzeit)
ht_defense_ratio = gegentore_1_halbzeit / (gegentore_1_halbzeit + gegentore_2_halbzeit)

profil_typ:
  "starte_stark"   wenn ht_attack_ratio > 0.55
  "finisher"       wenn ht_attack_ratio < 0.45
  "ausgeglichen"   sonst
```

## Output-Felder

Pro Team und Saison:

```json
{
  "team_id": 42,
  "season": 2025,
  "league_id": 78,
  "spiele_gesamt": 26,
  "tore_gesamt": 38,
  "gegentore_gesamt": 24,
  "timing_attack": {
    "0_15":  {"tore": 4, "rate": 0.154, "angriffs_index": 0.87},
    "16_30": {"tore": 7, "rate": 0.269, "angriffs_index": 1.52},
    "31_45": {"tore": 6, "rate": 0.231, "angriffs_index": 1.31},
    "46_60": {"tore": 5, "rate": 0.192, "angriffs_index": 1.09},
    "61_75": {"tore": 8, "rate": 0.308, "angriffs_index": 1.74},
    "76_90": {"tore": 8, "rate": 0.308, "angriffs_index": 1.74}
  },
  "timing_defense": {
    "0_15":  {"gegentore": 2, "rate": 0.077, "defensiv_index": 0.95},
    "16_30": {"gegentore": 3, "rate": 0.115, "defensiv_index": 0.88},
    "31_45": {"gegentore": 5, "rate": 0.192, "defensiv_index": 0.68},
    "46_60": {"gegentore": 4, "rate": 0.154, "defensiv_index": 0.76},
    "61_75": {"gegentore": 4, "rate": 0.154, "defensiv_index": 0.76},
    "76_90": {"gegentore": 6, "rate": 0.231, "defensiv_index": 0.62}
  },
  "ht_attack_ratio": 0.447,
  "ht_defense_ratio": 0.417,
  "profil_typ": "ausgeglichen",
  "p_goal_first_30_min": 0.42,
  "p_goal_last_15_min": 0.31,
  "comeback_index": 1.18,
  "computed_at": "2026-03-10T12:00:00Z"
}
```

## Datenbasis

- `fixture_events` (bereits vorhanden) → `event_type='Goal'`, `detail IN ('Normal Goal','Penalty')`, `elapsed`
- `fixtures` → für Heim/Auswärts-Kontext und Saisonfilter
- **0 extra API-Calls nötig** – alles aus bestehenden Daten berechenbar
- Tabelle: `team_timing_profile` (team_id, season, league_id, timing_json, computed_at)

## Abhängigkeiten zu anderen Pattern

- Keine direkten Abhängigkeiten (eigenständig aus API-Daten berechenbar)
- Liefert Daten an:
  - `ai-match-picks` (Timing-Profile als zusätzlicher Kontext für Claude)
  - `match-result-probability` (optionale Anreicherung für HT/FT-Ableitungen)

## Nutzen für Wettscheine/Analyse

- **Erstes Tor**: Wenn Team A in den ersten 30 Minuten stark ist und Team B schwach startet, erhöht sich die Wahrscheinlichkeit für "Team A erzielt das erste Tor"
- **Halbzeitergebnis**: ht_attack_ratio ist ein direktes Signal für HT-Over/Under
- **Comeback-Potential**: Hoher comeback_index zeigt, dass ein Team nach Rückstand häufig noch trifft – relevant für Live-Wetten und HT/FT-Kombis
- **Late Goals**: Hohe Tor-Rate in 76–90 deutet auf physische Stärke und Pressing-Fußball hin
- **Defensive Schwachstellen**: Klare Zeitfenster mit hohem defensiv_index zeigen, wann ein Team anfällig ist
