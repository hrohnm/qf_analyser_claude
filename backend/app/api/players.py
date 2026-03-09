from collections import defaultdict
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.fixture import Fixture
from app.models.fixture_events import FixtureEvent
from app.models.team import Team

router = APIRouter(prefix="/players", tags=["Players"])


class PlayerOverviewOut(BaseModel):
    player_id: int | None = None
    player_name: str
    team_id: int | None = None
    team_name: str | None = None
    team_logo_url: str | None = None
    matches: int
    goals: int
    assists: int
    yellow_cards: int
    red_cards: int
    substitutions: int
    events_total: int
    first_event_utc: str | None = None
    last_event_utc: str | None = None


@router.get("/overview", response_model=list[PlayerOverviewOut])
async def players_overview(
    season_year: int = Query(..., description="Saison-Jahr, z.B. 2025"),
    league_id: int | None = Query(None, description="Optional auf Liga filtern"),
    team_id: int | None = Query(None, description="Optional auf Team filtern"),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Aggregierte Spielerübersicht aus lokalen Match-Events (Tore, Vorlagen, Karten, etc.)."""
    stmt = (
        select(FixtureEvent, Fixture, Team)
        .join(Fixture, Fixture.id == FixtureEvent.fixture_id)
        .outerjoin(Team, Team.id == FixtureEvent.team_id)
        .where(Fixture.season_year == season_year)
    )
    if league_id is not None:
        stmt = stmt.where(Fixture.league_id == league_id)
    if team_id is not None:
        stmt = stmt.where(FixtureEvent.team_id == team_id)

    result = await db.execute(stmt)
    rows = result.all()

    stats: dict[str, dict] = {}

    def key_for(player_id: int | None, player_name: str | None) -> str:
        if player_id is not None:
            return f"id:{player_id}"
        return f"name:{(player_name or '').strip().lower()}"

    def ensure_player(
        player_id: int | None,
        player_name: str | None,
        event_team_id: int | None,
        event_team_name: str | None,
        event_team_logo: str | None,
    ) -> dict | None:
        name = (player_name or "").strip()
        if not name and player_id is None:
            return None

        k = key_for(player_id, name)
        if k not in stats:
            stats[k] = {
                "player_id": player_id,
                "player_name": name or f"Spieler {player_id}",
                "team_counts": defaultdict(int),
                "team_meta": {},
                "fixtures": set(),
                "goals": 0,
                "assists": 0,
                "yellow_cards": 0,
                "red_cards": 0,
                "substitutions": 0,
                "events_total": 0,
                "first_event_utc": None,
                "last_event_utc": None,
            }

        entry = stats[k]
        if event_team_id is not None:
            entry["team_counts"][event_team_id] += 1
            entry["team_meta"][event_team_id] = (event_team_name, event_team_logo)
        return entry

    for event, fixture, team in rows:
        e_team_id = event.team_id
        e_team_name = team.name if team else None
        e_team_logo = team.logo_url if team else None

        # Main event player
        main = ensure_player(event.player_id, event.player_name, e_team_id, e_team_name, e_team_logo)
        if main is not None:
            main["events_total"] += 1
            main["fixtures"].add(event.fixture_id)

            if event.event_type == "Goal":
                main["goals"] += 1
            if event.detail == "Yellow Card":
                main["yellow_cards"] += 1
            if event.detail in {"Red Card", "Second Yellow card"}:
                main["red_cards"] += 1
            if event.event_type == "subst":
                main["substitutions"] += 1

            if fixture.kickoff_utc is not None:
                if main["first_event_utc"] is None or fixture.kickoff_utc < main["first_event_utc"]:
                    main["first_event_utc"] = fixture.kickoff_utc
                if main["last_event_utc"] is None or fixture.kickoff_utc > main["last_event_utc"]:
                    main["last_event_utc"] = fixture.kickoff_utc

        # Assist player (can be absent from player column)
        if event.assist_id is not None or (event.assist_name or "").strip():
            assist = ensure_player(event.assist_id, event.assist_name, e_team_id, e_team_name, e_team_logo)
            if assist is not None:
                assist["assists"] += 1
                assist["fixtures"].add(event.fixture_id)
                if fixture.kickoff_utc is not None:
                    if assist["first_event_utc"] is None or fixture.kickoff_utc < assist["first_event_utc"]:
                        assist["first_event_utc"] = fixture.kickoff_utc
                    if assist["last_event_utc"] is None or fixture.kickoff_utc > assist["last_event_utc"]:
                        assist["last_event_utc"] = fixture.kickoff_utc

    out: list[PlayerOverviewOut] = []
    for entry in stats.values():
        team_display_id = None
        team_display_name = None
        team_display_logo = None
        if entry["team_counts"]:
            team_display_id = max(entry["team_counts"].items(), key=lambda x: x[1])[0]
            team_display_name, team_display_logo = entry["team_meta"].get(team_display_id, (None, None))

        out.append(PlayerOverviewOut(
            player_id=entry["player_id"],
            player_name=entry["player_name"],
            team_id=team_display_id,
            team_name=team_display_name,
            team_logo_url=team_display_logo,
            matches=len(entry["fixtures"]),
            goals=entry["goals"],
            assists=entry["assists"],
            yellow_cards=entry["yellow_cards"],
            red_cards=entry["red_cards"],
            substitutions=entry["substitutions"],
            events_total=entry["events_total"],
            first_event_utc=entry["first_event_utc"].isoformat() if entry["first_event_utc"] else None,
            last_event_utc=entry["last_event_utc"].isoformat() if entry["last_event_utc"] else None,
        ))

    out.sort(key=lambda x: (-x.goals, -x.assists, -x.matches, x.player_name.lower()))
    return out[offset: offset + limit]
