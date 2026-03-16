import logging
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.sync import router as sync_router
from app.api.fixtures import router as fixtures_router
from app.api.leagues import router as leagues_router
from app.api.players import router as players_router
from app.api.standings import router as standings_router
from app.api.teams import router as teams_router
from app.api.betting_slips import router as betting_slips_router
from app.api.admin import router as admin_router
from app.sync.client import api_client
from app.sync.jobs.sync_fixtures import sync_started_today_fixtures
from app.sync.live_refresh_runtime import live_refresh_controller

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)


async def _live_fixture_refresh_loop() -> None:
    while True:
        state = await live_refresh_controller.wait_until_next_run()
        try:
            result = await sync_started_today_fixtures()
            logger.info(
                "[LiveFixtureRefresh] interval=%ss leagues=%s fixtures=%s",
                state.interval_seconds,
                result.get("leagues", 0),
                result.get("fixtures", 0),
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("[LiveFixtureRefresh] periodic refresh failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    live_fixture_task: asyncio.Task | None = None
    if settings.live_fixture_refresh_enabled:
        live_fixture_task = asyncio.create_task(_live_fixture_refresh_loop())

    yield
    # Shutdown
    if live_fixture_task is not None:
        live_fixture_task.cancel()
        try:
            await live_fixture_task
        except asyncio.CancelledError:
            pass
    await api_client.close()


app = FastAPI(
    title="Quotenfabrik Analyser API",
    description="Sportwetten-Analyse auf Basis von api-football.com Daten",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sync_router, prefix="/api")
app.include_router(fixtures_router, prefix="/api")
app.include_router(leagues_router, prefix="/api")
app.include_router(players_router, prefix="/api")
app.include_router(standings_router, prefix="/api")
app.include_router(teams_router, prefix="/api")
app.include_router(betting_slips_router, prefix="/api")
app.include_router(admin_router, prefix="/api")


@app.get("/")
async def root():
    return {"status": "ok", "app": "Quotenfabrik Analyser", "version": "0.1.0"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
