import logging
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
from app.sync.client import api_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown
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


@app.get("/")
async def root():
    return {"status": "ok", "app": "Quotenfabrik Analyser", "version": "0.1.0"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
