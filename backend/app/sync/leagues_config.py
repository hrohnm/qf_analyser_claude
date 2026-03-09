# api-football.com league IDs for all target leagues
# Verified IDs for the 2024/2025 season
LEAGUES: list[dict] = [
    # Germany
    {"id": 78,  "name": "Bundesliga",       "country": "Germany", "tier": 1},
    {"id": 79,  "name": "2. Bundesliga",    "country": "Germany", "tier": 2},
    {"id": 80,  "name": "3. Liga",          "country": "Germany", "tier": 3},
    # France
    {"id": 61,  "name": "Ligue 1",          "country": "France",  "tier": 1},
    {"id": 62,  "name": "Ligue 2",          "country": "France",  "tier": 2},
    {"id": 63,  "name": "National",         "country": "France",  "tier": 3},
    # Italy
    {"id": 135, "name": "Serie A",          "country": "Italy",   "tier": 1},
    {"id": 136, "name": "Serie B",          "country": "Italy",   "tier": 2},
    {"id": 137, "name": "Serie C",          "country": "Italy",   "tier": 3},
    # Spain
    {"id": 140, "name": "La Liga",          "country": "Spain",   "tier": 1},
    {"id": 141, "name": "Segunda División", "country": "Spain",   "tier": 2},
    {"id": 142, "name": "Primera Federación","country": "Spain",  "tier": 3},
    # England
    {"id": 39,  "name": "Premier League",   "country": "England", "tier": 1},
    {"id": 40,  "name": "Championship",     "country": "England", "tier": 2},
    {"id": 41,  "name": "League One",       "country": "England", "tier": 3},
    # Turkey
    {"id": 203, "name": "Süper Lig",        "country": "Turkey",  "tier": 1},
    {"id": 204, "name": "1. Lig",           "country": "Turkey",  "tier": 2},
    {"id": 205, "name": "2. Lig",           "country": "Turkey",  "tier": 3},
]

LEAGUE_IDS = [l["id"] for l in LEAGUES]
