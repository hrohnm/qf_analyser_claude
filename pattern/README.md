# Pattern Library

Dieses Verzeichnis sammelt wiederverwendbare Analyse-Pattern.

## Ziel

- Pro fachlicher Fragestellung ein eigener Unterordner
- Klare Trennung zwischen Konzept, Datenbedarf und Implementierungsplan
- Nachvollziehbare Weiterentwicklung ohne Ad-hoc-Logik

## Struktur pro Pattern

Jedes Pattern bekommt einen Ordner:

`pattern/<pattern-name>/`

Empfohlene Dateien:

- `README.md` – fachliches Ziel, Annahmen, Ergebnis
- `data-contract.md` – benötigte Datenfelder/Tabellen/APIs
- `formula.md` – Berechnungslogik und Scoring
- `next-steps.md` – konkrete Implementierungsschritte

## Namenskonvention

- Kleinschreibung
- Wörter mit Bindestrich
- Beispiel: `injury-impact-player`

## Reifegrad

Optional pro Pattern kennzeichnen:

- `draft` – erste Idee
- `validated` – fachlich geprüft
- `production` – implementiert und aktiv genutzt

## Vorhandene Pattern

- `injury-impact-player`
- `team-current-form`
- `team-elo`
- `goal-probability-weighted`
