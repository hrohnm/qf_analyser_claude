# API-Football v3 – Vollständige Dokumentation

Base URL: `https://v3.football.api-sports.io`
Header: `x-apisports-key: <API_KEY>`
Konto: Pro Plan, 7.500 Calls/Tag

## Übersicht aller Endpoints

| Datei | Kategorie | Endpoints | Batch? |
|---|---|---|---|
| [00-overview.md](00-overview.md) | Status / Meta | `/status`, `/timezone`, `/countries` | ✗ |
| [01-leagues.md](01-leagues.md) | Ligen | `/leagues`, `/leagues/seasons` | ✗ |
| [02-teams.md](02-teams.md) | Teams | `/teams`, `/teams/statistics`, `/teams/countries`, `/teams/seasons` | ✗ |
| [03-players.md](03-players.md) | Spieler | `/players`, `/players/squads`, `/players/seasons`, `/sidelined`, `/trophies` | ✗ |
| [04-fixtures.md](04-fixtures.md) | Spiele | `/fixtures`, `/fixtures/rounds`, `/fixtures/headtohead`, `/fixtures/statistics`, `/fixtures/events`, `/fixtures/lineups`, `/fixtures/players` | ✗ |
| [05-standings.md](05-standings.md) | Tabellen | `/standings` | ✗ |
| [06-odds.md](06-odds.md) | Quoten | `/odds`, `/odds/live`, `/odds/mapping`, `/odds/bookmakers`, `/odds/bets` | ✗ |
| [07-predictions.md](07-predictions.md) | Vorhersagen | `/predictions` | ✗ |
| [08-coachs.md](08-coachs.md) | Trainer | `/coachs` | ✗ |
| [09-injuries.md](09-injuries.md) | Verletzungen | `/injuries` | ✗ |
| [10-transfers.md](10-transfers.md) | Transfers | `/transfers` | ✗ |

## Batch-Calls: Ergebnis

> **Kein einziger Endpoint unterstützt echte Batch-Abfragen (mehrere IDs gleichzeitig).**

Getesteter Versuch: `GET /odds?fixtures=1378969-1378970` →
```json
{"errors": {"fixtures": "The Fixtures field do not exist."}}
```

Ausnahme: `/injuries` akzeptiert `?ids=id1-id2-...-id20` (bis 20 Fixture-IDs, Bindestrich-getrennt).
→ Wird bereits in unserem Sync genutzt.

## Quotenübersicht (calls/request)

Alle Endpoints verbrauchen **1 Call pro Request**, unabhängig von der Antwortgröße.
Paginierung bei großen Resultsets via `?page=N`.
