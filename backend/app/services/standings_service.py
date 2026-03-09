"""
Berechnet die Tabelle einer Liga aus den in der DB gespeicherten Fixture-Daten.
Keine API-Calls nötig – alles aus lokalen Daten.

Regeln:
  Sieg   = 3 Punkte
  Unentschieden = 1 Punkt
  Niederlage = 0 Punkte
  Sortierung: Punkte → Tordifferenz → Tore für → alphabetisch
"""
from dataclasses import dataclass, field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fixture import Fixture
from app.models.team import Team

FINISHED_STATUSES = {"FT", "AET", "PEN"}


@dataclass
class TeamStanding:
    team_id: int
    team_name: str
    logo_url: str
    played: int = 0
    won: int = 0
    drawn: int = 0
    lost: int = 0
    goals_for: int = 0
    goals_against: int = 0
    points: int = 0
    form: list[str] = field(default_factory=list)  # last 5: 'W', 'D', 'L'

    @property
    def goal_diff(self) -> int:
        return self.goals_for - self.goals_against

    def to_dict(self, rank: int) -> dict:
        return {
            "rank": rank,
            "team_id": self.team_id,
            "team_name": self.team_name,
            "logo_url": self.logo_url,
            "played": self.played,
            "won": self.won,
            "drawn": self.drawn,
            "lost": self.lost,
            "goals_for": self.goals_for,
            "goals_against": self.goals_against,
            "goal_diff": self.goal_diff,
            "points": self.points,
            "form": "".join(self.form[-5:]),
        }


def _logo_url(team_id: int) -> str:
    return f"https://media.api-sports.io/football/teams/{team_id}.png"


async def calculate_standings(
    db: AsyncSession,
    league_id: int,
    season_year: int,
    up_to_matchday: int | None = None,
) -> list[dict]:
    """
    Berechnet die Ligatabelle aus abgeschlossenen Spielen.
    up_to_matchday: wenn gesetzt, werden nur Spiele bis inkl. diesem Spieltag berücksichtigt.
    """
    stmt = (
        select(Fixture, Team)
        .join(Team, Team.id == Fixture.home_team_id)
        .where(
            Fixture.league_id == league_id,
            Fixture.season_year == season_year,
            Fixture.status_short.in_(FINISHED_STATUSES),
        )
        .order_by(Fixture.kickoff_utc)
    )
    if up_to_matchday is not None:
        stmt = stmt.where(Fixture.matchday <= up_to_matchday)

    result = await db.execute(stmt)
    rows = result.all()

    if not rows:
        return []

    # Collect all team IDs to load names
    team_ids: set[int] = set()
    for fixture, _ in rows:
        team_ids.add(fixture.home_team_id)
        team_ids.add(fixture.away_team_id)

    teams_result = await db.execute(select(Team).where(Team.id.in_(team_ids)))
    teams: dict[int, Team] = {t.id: t for t in teams_result.scalars()}

    standings: dict[int, TeamStanding] = {}

    def get_or_create(team_id: int) -> TeamStanding:
        if team_id not in standings:
            team = teams.get(team_id)
            standings[team_id] = TeamStanding(
                team_id=team_id,
                team_name=team.name if team else f"Team {team_id}",
                logo_url=_logo_url(team_id),
            )
        return standings[team_id]

    for fixture, _ in rows:
        home_goals = fixture.home_score
        away_goals = fixture.away_score

        if home_goals is None or away_goals is None:
            continue

        home = get_or_create(fixture.home_team_id)
        away = get_or_create(fixture.away_team_id)

        home.played += 1
        away.played += 1
        home.goals_for += home_goals
        home.goals_against += away_goals
        away.goals_for += away_goals
        away.goals_against += home_goals

        if home_goals > away_goals:
            home.won += 1
            home.points += 3
            home.form.append("W")
            away.lost += 1
            away.form.append("L")
        elif home_goals == away_goals:
            home.drawn += 1
            home.points += 1
            home.form.append("D")
            away.drawn += 1
            away.points += 1
            away.form.append("D")
        else:
            away.won += 1
            away.points += 3
            away.form.append("W")
            home.lost += 1
            home.form.append("L")

    sorted_teams = sorted(
        standings.values(),
        key=lambda s: (-s.points, -s.goal_diff, -s.goals_for, s.team_name),
    )

    return [team.to_dict(rank=i + 1) for i, team in enumerate(sorted_teams)]


async def get_matchdays(
    db: AsyncSession,
    league_id: int,
    season_year: int,
) -> list[int]:
    """Gibt alle vorhandenen Spieltags-Nummern für eine Liga/Saison zurück."""
    from sqlalchemy import distinct
    stmt = (
        select(distinct(Fixture.matchday))
        .where(
            Fixture.league_id == league_id,
            Fixture.season_year == season_year,
            Fixture.matchday.is_not(None),
        )
        .order_by(Fixture.matchday)
    )
    result = await db.execute(stmt)
    return [row[0] for row in result.all()]
