from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.standings_service import calculate_standings, get_matchdays

router = APIRouter(prefix="/standings", tags=["Tabelle"])


@router.get("/{league_id}")
async def league_standings(
    league_id: int,
    season_year: int = Query(..., description="Saison-Jahr, z.B. 2024"),
    up_to_matchday: int | None = Query(None, description="Tabelle bis inkl. Spieltag N"),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """
    Berechnet die Ligatabelle aus lokalen Fixture-Daten.
    Kein API-Call nötig.
    """
    return await calculate_standings(db, league_id, season_year, up_to_matchday)


@router.get("/{league_id}/matchdays")
async def league_matchdays(
    league_id: int,
    season_year: int = Query(..., description="Saison-Jahr"),
    db: AsyncSession = Depends(get_db),
) -> list[int]:
    """Gibt alle verfügbaren Spieltage für eine Liga/Saison zurück."""
    return await get_matchdays(db, league_id, season_year)
