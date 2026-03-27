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
    {"id": 135, "name": "Serie A",              "country": "Italy",   "tier": 1},
    {"id": 136, "name": "Serie B",              "country": "Italy",   "tier": 2},
    {"id": 138, "name": "Serie C - Girone A",   "country": "Italy",   "tier": 3},
    {"id": 942, "name": "Serie C - Girone B",   "country": "Italy",   "tier": 3},
    {"id": 943, "name": "Serie C - Girone C",   "country": "Italy",   "tier": 3},
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
    # European Cups
    {"id": 2,   "name": "UEFA Champions League", "country": "Europe", "tier": 0},
    {"id": 3,   "name": "UEFA Europa League",    "country": "Europe", "tier": 0},
    {"id": 848, "name": "UEFA Conference League","country": "Europe", "tier": 0},
    # International Friendlies & Nations League
    {"id": 10,  "name": "International Friendlies",             "country": "World", "tier": 0},
    {"id": 5,   "name": "UEFA Nations League",                  "country": "Europe", "tier": 0},
    # FIFA World Cup & Qualifications
    {"id": 1,   "name": "FIFA World Cup",                        "country": "World", "tier": 0},
    {"id": 32,  "name": "WC Qualification - South America",      "country": "World", "tier": 0},
    {"id": 33,  "name": "WC Qualification - Asia",               "country": "World", "tier": 0},
    {"id": 34,  "name": "WC Qualification - Africa",             "country": "World", "tier": 0},
    {"id": 31,  "name": "WC Qualification - North America",      "country": "World", "tier": 0},
    {"id": 35,  "name": "WC Qualification - Europe (UEFA)",      "country": "World", "tier": 0},
    {"id": 36,  "name": "WC Qualification - Oceania",            "country": "World", "tier": 0},
]

LEAGUE_IDS = [l["id"] for l in LEAGUES]

# ── Companion leagues for cross-competition team statistics ───────────────────
# When computing team-level patterns (Elo, Form, GoalTiming, HomeAdv) for a
# domestic league, these additional competition IDs are included so that a
# team's European cup results also inform its statistics.
#
# Tier 1  → CL + EL + ECL
# Tier 2  → EL + ECL  (teams rarely qualify for CL)
# Tier 3  → ECL only
# Cups (2, 3, 848) → no companions (they are the extra source for others)
CUP_COMPANIONS: dict[int, list[int]] = {
    # Germany
    78:  [2, 3, 848],  # Bundesliga
    79:  [3, 848],     # 2. Bundesliga
    80:  [848],        # 3. Liga
    # France
    61:  [2, 3, 848],  # Ligue 1
    62:  [3, 848],     # Ligue 2
    63:  [848],        # National
    # Italy
    135: [2, 3, 848],  # Serie A
    136: [3, 848],     # Serie B
    138: [848],        # Serie C - Girone A
    942: [848],        # Serie C - Girone B
    943: [848],        # Serie C - Girone C
    # Spain
    140: [2, 3, 848],  # La Liga
    141: [3, 848],     # Segunda División
    142: [848],        # Primera Federación
    # England
    39:  [2, 3, 848],  # Premier League
    40:  [3, 848],     # Championship
    41:  [848],        # League One
    # Turkey
    203: [2, 3, 848],  # Süper Lig
    204: [3, 848],     # 1. Lig
    205: [848],        # 2. Lig
}
